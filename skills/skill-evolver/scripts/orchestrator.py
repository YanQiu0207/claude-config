#!/usr/bin/env python3
"""Evolve loop orchestrator + CLI entrypoint.

This module owns the "glue" that chains the individual Phase functions
(defined in ``evolve_loop.py``) into a complete run:

  * ``_eval_holdout_or_none`` — holdout-split soft fetch used by the
    baseline + gate paths
  * ``run_evolve_loop`` — the canonical 8-Phase orchestrator; calls
    phase_0..phase_8 in order, owns the iteration counter, and carries
    the best-so-far state across iterations
  * ``main`` — the ``python evolve_loop.py`` CLI entry (argparse wiring
    + flag dispatch for --info / --cleanup / --run / --dry-run)

Split rationale (iter 18): ``run_evolve_loop`` was the single biggest
function in the repo (~240 lines) and ``main`` another ~150 lines of
argparse plumbing. Together they were half of evolve_loop.py. Keeping
the Phase definitions in one file (``evolve_loop.py``) and the
"assemble + drive" logic here makes each file's purpose greppable
from its name.

``evolve_loop.py`` still exposes both functions via re-export, so the
``python scripts/evolve_loop.py <args>`` entry point and any existing
``from evolve_loop import run_evolve_loop`` callers keep working.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import require_creator, CreatorNotFoundError, find_workspace
from aggregate_results import parse_results_tsv, calculate_summary
from evaluators import get_evaluator, parse_evaluator_from_plan, Evaluator
from gate import phase_6_gate_decision
from llm import phase_2_3_ideate_and_modify, auto_construct_gt
from cleanup import (
    cleanup_best_versions, cleanup_eval_outputs, _try_launch_eval_viewer,
    _prepare_viewer_data,
)
from evolve_loop import (  # phase definitions live in evolve_loop.py
    phase_0_setup, phase_1_review, phase_4_commit,
    phase_7_log, phase_8_loop_control,
    git_revert_last, save_best_version, _list_untracked,
)


def _eval_holdout_or_none(evaluator, skill_path: Path,
                          gt_path: Path) -> float | None:
    """Run the evaluator on the holdout split and return the pass rate.

    Returns None when the GT has no holdout cases (so the evaluator either
    raises or reports zero assertions). The gate then degrades to dev-only
    quality logic.
    """
    try:
        result = evaluator.full_eval(skill_path, gt_path, split="holdout")
    except Exception:
        return None
    if not result or result.get("total_assertions", 0) == 0:
        return None
    return result.get("pass_rate")


def _eval_regression_or_none(evaluator, skill_path: Path,
                             gt_path: Path) -> float | None:
    """Run the evaluator on the regression split and return the pass rate.

    Mirror of ``_eval_holdout_or_none``. Returns None when the GT has no
    regression cases, in which case the gate degrades to treating the
    regression dimension as a neutral pass (1.0). Previously the loop
    hardcoded ``regression_pass=1.0`` unconditionally, so the regression
    dimension of the 5-way AND gate was a no-op even when the GT *did*
    carry a regression split with scoreable (deterministic) assertions.
    """
    try:
        result = evaluator.full_eval(skill_path, gt_path, split="regression")
    except Exception:
        return None
    if not result or result.get("total_assertions", 0) == 0:
        return None
    return result.get("pass_rate")


def _resolve_gate_thresholds(gt_path: Path, plan_path: Path | None = None) -> dict:
    """Resolve Phase 6 gate thresholds — noise-aware and GT-adaptive.

    Replaces the previously hardcoded ``{min_delta: 0.01,
    noise_threshold: 0.005}``, which sat BELOW the run-to-run drift of
    LLM grading, so most keep/discard decisions were indistinguishable
    from luck. Starts from gate.py's defaults, widens the bands when the
    GT is LLM-graded or small (per references/eval_strategy.md), and lets
    explicit ``key: value`` overrides in evolve_plan.md win.
    """
    th = {
        "min_delta": 0.02,
        "trigger_tolerance": 0.05,
        "max_token_increase": 0.20,
        "max_latency_increase": 0.20,
        "regression_tolerance": 0.05,
        "noise_threshold": 0.01,
    }
    try:
        data = json.loads(Path(gt_path).read_text(encoding="utf-8"))
        cases = data if isinstance(data, list) else data.get("evals", [])
        n_dev = sum(1 for c in cases if c.get("split", "dev") == "dev")
        llm_graded = any(
            a.get("type") in ("path_hit", "fact_coverage")
            for c in cases for a in c.get("assertions", []))
    except Exception:
        n_dev, llm_graded = 0, False
    if llm_graded:
        # LLM grading drifts ~10%+ run to run — demand a delta above the
        # band and treat sub-band changes as noise, not a real improvement.
        th["min_delta"] = max(th["min_delta"], 0.05)
        th["noise_threshold"] = max(th["noise_threshold"], 0.03)
    if 0 < n_dev <= 15:
        # Few cases → one case flipping is a large pass_rate swing.
        th["min_delta"] = max(th["min_delta"], 0.05)
    if plan_path and Path(plan_path).exists():
        try:
            text = Path(plan_path).read_text(encoding="utf-8")
            for key in list(th):
                m = re.search(rf"^\s*{key}\s*:\s*([0-9.]+)", text, re.MULTILINE)
                if m:
                    th[key] = float(m.group(1))
        except Exception:
            pass
    return th


# ─────────────────────────────────────────────
# Resume + budget helpers (pure — unit-tested in tests/test_core_logic.py)
# ─────────────────────────────────────────────

def _recover_resume_state(prior_rows: list[dict]) -> dict | None:
    """Derive resume parameters from a prior run's results.tsv rows.

    Returns None when there is no real prior iteration to resume from (an
    empty/missing tsv, or only the baseline row at iteration 0). Otherwise
    returns ``{start_iteration, current_layer, prior_iterations}`` so the
    loop can continue the iteration counter and layer search instead of
    restarting from a fresh baseline.
    """
    iters = [r["iteration"] for r in prior_rows
             if isinstance(r.get("iteration"), int) and r["iteration"] >= 1]
    if not iters:
        return None
    last_layer = prior_rows[-1].get("layer") or "body"
    if last_layer not in ("description", "body", "script"):
        last_layer = "body"
    return {
        "start_iteration": max(iters) + 1,
        "current_layer": last_layer,
        "prior_iterations": len(iters),
    }


def _budget_status(tokens_spent: int, elapsed_seconds: float,
                   max_total_tokens: int | None,
                   max_wall_seconds: float | None) -> str | None:
    """Return a human-readable stop reason if a budget is exhausted, else None.

    The unattended loop's only stop control used to be ``max_iterations``
    (a count); for semantic GTs a single iteration can burn a large number
    of tokens / minutes, so a runaway run had no token or wall-clock
    safety valve. These two optional ceilings provide it.
    """
    if max_total_tokens is not None and tokens_spent >= max_total_tokens:
        return (f"token budget reached "
                f"({tokens_spent} >= {max_total_tokens})")
    if max_wall_seconds is not None and elapsed_seconds >= max_wall_seconds:
        return (f"wall-clock budget reached "
                f"({elapsed_seconds:.0f}s >= {max_wall_seconds:.0f}s)")
    return None


# ─────────────────────────────────────────────
# Full auto loop
# ─────────────────────────────────────────────

def run_evolve_loop(skill_path: Path, gt_path: Path, workspace: Path,
                    max_iterations: int = 20, model: str | None = None,
                    verbose: bool = True,
                    evaluator: Evaluator | None = None,
                    dry_run: bool = False,
                    resume: bool = False,
                    max_total_tokens: int | None = None,
                    max_wall_seconds: float | None = None) -> dict:
    """Run the complete 8-phase evolve loop.

    This is the REAL auto loop. Phase 2+3 use claude -p for LLM reasoning.
    Evaluation uses the pluggable Evaluator interface.

    Args:
        evaluator: Pluggable evaluator instance. If None, auto-detects from
                   evolve_plan.md config or defaults to CreatorEvaluator.
        dry_run: Preview mode. Phases 0..3 run normally (setup, baseline,
                 first-iteration review, ideate+modify), but the loop
                 breaks BEFORE phase_4_commit — no git commit happens,
                 no gate decision, no log write beyond the baseline.
                 The mutation proposal from phase_2_3 is returned in the
                 result dict so the user can inspect what would have
                 been changed before allowing a real run.
    """
    # Initialize evaluator
    if evaluator is None:
        plan_path = workspace / "evolve" / "evolve_plan.md"
        eval_config = parse_evaluator_from_plan(plan_path)
        if model:
            eval_config["model"] = model
        evaluator = get_evaluator(eval_config)

    def log(msg):
        if verbose:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {msg}", file=sys.stderr, flush=True)

    log("=" * 60)
    log("EVOLVE LOOP START")
    log(f"Skill: {skill_path}")
    log(f"GT: {gt_path}")
    log(f"Max iterations: {max_iterations}")
    log(f"Evaluator: {evaluator.info()}")
    log("=" * 60)

    # Creator dependency check (fail fast)
    log("Checking skill-creator dependency...")
    creator_path = require_creator()
    log(f"Creator found: {creator_path}")

    # Phase 0: Setup
    log("Phase 0: Setup")
    setup = phase_0_setup(skill_path, gt_path, workspace)
    evolve_dir = Path(setup["evolve_dir"])

    # Resume detection. When --resume is set and the workspace already
    # carries real iterations, recover the iteration counter + layer from
    # results.tsv and treat the current (best-kept) working tree as the
    # baseline, instead of writing a fresh baseline row / E0 snapshot.
    resume_state = _recover_resume_state(parse_results_tsv(workspace)) if resume else None
    if resume:
        if resume_state:
            log(f"RESUME: {resume_state['prior_iterations']} prior iteration(s) "
                f"found — continuing at iteration {resume_state['start_iteration']} "
                f"on layer '{resume_state['current_layer']}' "
                f"(current tree re-evaluated as baseline)")
        else:
            log("RESUME requested but no prior iterations found — "
                "starting a fresh baseline")

    # Resolve gate thresholds once (noise-aware, GT-adaptive, plan-overridable)
    # instead of hardcoding a sub-noise min_delta into the gate call below.
    gate_thresholds = _resolve_gate_thresholds(
        gt_path, workspace / "evolve" / "evolve_plan.md")
    log(f"Gate thresholds: min_delta={gate_thresholds['min_delta']}, "
        f"noise={gate_thresholds['noise_threshold']}")

    l1 = evaluator.quick_gate(skill_path, gt_path)
    if not l1["pass"]:
        log(f"ABORT: L1 gate failed — {l1['errors']}")
        return {"success": False, "error": "L1 gate failed"}

    # Baseline eval — runs both dev and holdout so the gate can compare
    # both surfaces from iteration 1 onwards. holdout is soft-fetched and
    # may be None if the GT has no holdout split.
    log("Phase 0: Baseline eval")
    baseline = evaluator.full_eval(skill_path, gt_path)
    baseline_rate = baseline["pass_rate"]
    # Red-team finding #7 (iter 30): reject empty dev split. With zero
    # assertions, pass_rate collapses to 0.0 (the `if total_t else 0`
    # guard in LocalEvaluator), giving the gate no signal at all and
    # confusing the user as to why no iterations ever improve. An
    # empty dev GT is a data-prep error, not a valid loop state.
    if baseline.get("total_assertions", 0) == 0:
        msg = (
            f"Phase 0 baseline: GT at {gt_path} has 0 assertions in the "
            f"dev split. The evolve loop needs at least one scoreable "
            f"case to produce a signal for the Phase 6 gate. Add at "
            f"least one dev case to evals.json (see references/"
            f"eval_strategy.md for templates) or pass a different GT "
            f"via --gt."
        )
        log(f"ABORT: {msg}")
        return {"success": False, "error": msg}
    baseline_holdout = _eval_holdout_or_none(evaluator, skill_path, gt_path)
    baseline_regression = _eval_regression_or_none(evaluator, skill_path, gt_path)
    baseline_trigger = baseline.get("trigger_f1")
    log(f"Baseline: {baseline['total_passed']}/{baseline['total_assertions']} = {baseline_rate:.0%}"
        + (f" | holdout {baseline_holdout:.0%}" if baseline_holdout is not None else " | holdout n/a")
        + (f" | regression {baseline_regression:.0%}" if baseline_regression is not None else " | regression n/a")
        + (f" | trigger_f1 {baseline_trigger:.2f}" if baseline_trigger is not None else " | trigger_f1 n/a"))

    # On a fresh run, persist the baseline trace (iteration-E0/cases/) and
    # snapshot E0 so the FIRST iteration's Phase 1/Phase 2 Meta-Harness
    # diagnosis has real baseline failure cases to grep, not just an
    # aggregate number. On resume these already exist from the prior run, so
    # we skip re-writing the baseline row / re-snapshotting E0.
    if resume_state is None:
        phase_7_log(workspace, 0, "baseline", baseline_rate * 100, 0.0,
                    baseline.get("trigger_f1", 1.0), 0, "pass", "baseline", "-",
                    "initial baseline", eval_result=baseline, split="dev")
        save_best_version(skill_path, workspace, 0)

    best_rate = baseline_rate
    best_holdout = baseline_holdout
    best_regression = baseline_regression
    if resume_state is not None:
        # Continue the prior layer search rather than restarting it.
        current_layer = resume_state["current_layer"]
        start_iteration = resume_state["start_iteration"]
    else:
        # Layer start is capability-conditional, not hardcoded. The description
        # layer optimizes trigger F1; if the evaluator can't produce a trigger
        # signal (e.g. the deterministic LocalEvaluator, whose full_eval omits
        # trigger_f1), starting there is wheel-spinning — no metric to judge the
        # change. Only start at "description" when the baseline actually carried
        # a trigger_f1 (CreatorEvaluator with a working trigger eval); otherwise
        # start at "body" exactly as before. This keeps the deterministic
        # default path's behavior unchanged.
        current_layer = "description" if baseline_trigger is not None else "body"
        start_iteration = 1
    log(f"Starting layer: {current_layer}"
        + ("" if (resume_state or baseline_trigger is not None)
           else " (no trigger_f1 signal — skipping description layer)"))

    # Budget guardrails (B3): cumulative eval tokens + wall-clock since the
    # loop body starts. max_iterations alone can't bound a runaway semantic
    # run where a single iteration is expensive. Both ceilings are optional.
    loop_start = time.time()
    tokens_spent = baseline.get("tokens", 0)
    stop_reason = None

    for iteration in range(start_iteration, max_iterations + 1):
        # B3: stop before doing expensive work if a budget is exhausted.
        stop_reason = _budget_status(
            tokens_spent, time.time() - loop_start,
            max_total_tokens, max_wall_seconds)
        if stop_reason:
            log(f"BUDGET STOP: {stop_reason}")
            break

        log("")
        log(f"{'=' * 40}")
        log(f"ITERATION {iteration}/{max_iterations}")
        log(f"{'=' * 40}")
        t0 = time.time()

        # Phase 1: Review
        log("Phase 1: Review")
        review = phase_1_review(workspace, skill_path)
        log(f"  {review['iterations']} iters, {review['keeps']} keeps, stuck={review['stuck']}")

        # Snapshot untracked files BEFORE phase_2_3 so we can diff
        # after the mutation runs and pass the resulting new_files list
        # to phase_4_commit. This lets Layer 3 mutations add new files
        # (iter 25 / #1) without re-opening iter 8's `git add -A`
        # footgun — only the files the mutation actually created are
        # staged, any user-dropped debris is ignored.
        untracked_before = _list_untracked(skill_path)

        # Phase 2+3: Ideate and Modify (via claude -p)
        log("Phase 2+3: Ideate and Modify (calling claude -p)")
        result_23 = phase_2_3_ideate_and_modify(
            skill_path, workspace, review, gt_path, current_layer, model)
        log(f"  Result: changed={result_23['changed']}, {result_23['description']}")

        if not result_23["changed"]:
            log("  No changes — stopping")
            phase_7_log(workspace, iteration, "-", best_rate * 100, 0.0,
                        1.0, 0, "pass", "exhausted", current_layer, "no improvement found")
            break

        # Compute mutation-added new files (iter 25). Empty set if the
        # mutation only edited tracked files, which is the common case.
        untracked_after = _list_untracked(skill_path)
        new_files = sorted(untracked_after - untracked_before)
        if new_files:
            log(f"  Phase 2+3 added {len(new_files)} new file(s): {', '.join(new_files[:5])}"
                + (f" (+{len(new_files) - 5} more)" if len(new_files) > 5 else ""))

        # Dry-run: stop here, before Phase 4 commits anything. Revert
        # the mutation first so the working tree matches what Phase 0
        # started with. The loop returns the proposed change so the
        # caller can inspect it.
        if dry_run:
            log("DRY-RUN: phase_2_3 proposed a mutation — reverting working tree and exiting")
            subprocess.run(
                ["git", "checkout", "--", "."], cwd=str(skill_path),
                capture_output=True, text=True, timeout=10,
            )
            # Also remove the mutation-added untracked files so the
            # tree matches the pre-iteration state exactly.
            for nf in new_files:
                try:
                    (skill_path / nf).unlink(missing_ok=True)
                except OSError:
                    pass
            return {
                "success": True,
                "dry_run": True,
                "baseline_pass_rate": baseline_rate,
                "proposed_mutation": result_23,
                "proposed_new_files": new_files,
                "best_metric": best_rate,
                "iterations_run": 1,
            }

        # Phase 4: Commit — pass mutation-added new files explicitly
        log("Phase 4: Commit")
        commit = phase_4_commit(
            skill_path, current_layer, result_23["description"],
            new_files=new_files,
        )
        if not commit["success"]:
            log(f"  Commit failed: {commit.get('error')}")
            continue
        log(f"  Committed: {commit['commit_hash']}")

        # Phase 5: Verify
        log("Phase 5: Verify")
        l1 = evaluator.quick_gate(skill_path, gt_path)
        log(f"  L1: {'PASS' if l1['pass'] else 'FAIL'}")
        if not l1["pass"]:
            # Red-team finding #8 (iter 30): check revert actually
            # succeeded. If git revert fails (merge conflict, detached
            # HEAD, hook veto, etc.) and we keep iterating, the broken
            # mutation contaminates the next iteration's baseline and
            # the entire run becomes unreliable. Abort instead.
            revert = git_revert_last(skill_path)
            if not revert.get("success"):
                msg = (
                    f"L1 fail at iter {iteration}; git revert ALSO failed "
                    f"({revert.get('output', 'no output')}). Working tree "
                    f"is in an undefined state. Aborting loop."
                )
                log(f"  ABORT: {msg}")
                phase_7_log(workspace, iteration, commit["commit_hash"], 0, -(best_rate*100),
                            1.0, 0, "fail", "crash", current_layer, msg)
                return {"success": False, "error": msg,
                        "baseline_rate": baseline_rate, "best_rate": best_rate}
            phase_7_log(workspace, iteration, commit["commit_hash"], 0, -(best_rate*100),
                        1.0, 0, "fail", "discard", current_layer,
                        f"L1 fail: {result_23['description']}")
            continue

        # L2 eval (uses pluggable evaluator) — dev + holdout so the gate
        # has both surfaces. holdout is soft-fetched (None if no split).
        log("  L2 eval...")
        new_eval = evaluator.full_eval(skill_path, gt_path)
        new_rate = new_eval["pass_rate"]
        new_holdout = _eval_holdout_or_none(evaluator, skill_path, gt_path)
        new_regression = _eval_regression_or_none(evaluator, skill_path, gt_path)
        tokens_spent += new_eval.get("tokens", 0)
        delta = new_rate - best_rate
        ho_msg = (f" | holdout {new_holdout:.0%}" if new_holdout is not None else "")
        log(f"  L2: {new_eval.get('total_passed', '?')}/{new_eval.get('total_assertions', '?')} = {new_rate:.0%} (delta: {delta:+.0%}){ho_msg}")
        je = new_eval.get("judge_errors", 0)
        if je:
            log(f"  WARN: {je} LLM judgment(s) were indeterminate (backend "
                f"error/timeout) and defaulted to FALSE — this pass_rate is "
                f"downward-biased and low-confidence.")

        # Phase 6: Gate (with real metrics from evaluator, incl. holdout)
        log("Phase 6: Gate")
        # Real 5-dim gate inputs. trigger_f1 / regression_pass were
        # previously hardcoded to 1.0, making 2 of the 5 AND-gate
        # dimensions no-ops. Now they read real values when available and
        # fall back to a neutral 1.0 only when there's genuinely no signal:
        #   · trigger_f1: present iff the evaluator's full_eval emitted it
        #     (CreatorEvaluator with a working trigger eval). LocalEvaluator
        #     omits it → .get(...,1.0) keeps the old neutral behavior.
        #   · regression_pass: present iff the GT has a regression split with
        #     scoreable assertions; None → neutral 1.0.
        gate = phase_6_gate_decision(
            {"pass_rate": new_rate, "holdout_pass_rate": new_holdout,
             "l1_pass": True, "trigger_f1": new_eval.get("trigger_f1", 1.0),
             "tokens_mean": new_eval.get("tokens", 0),
             "duration_mean": new_eval.get("duration", 0.0),
             "regression_pass": new_regression if new_regression is not None else 1.0},
            {"pass_rate": best_rate, "holdout_pass_rate": best_holdout,
             "trigger_f1": baseline.get("trigger_f1", 1.0),
             "tokens_mean": baseline.get("tokens", 0),
             "duration_mean": baseline.get("duration", 0.0),
             "regression_pass": best_regression if best_regression is not None else 1.0},
            gate_thresholds
        )
        decision = gate["decision"]
        log(f"  Decision: {decision}")
        for r in gate.get("reasons", []):
            log(f"    · {r}")

        if decision == "keep":
            best_rate = new_rate
            if new_holdout is not None:
                best_holdout = new_holdout
            if new_regression is not None:
                best_regression = new_regression
            save_best_version(skill_path, workspace, iteration)
            log(f"  KEEP — new best: dev {best_rate:.0%}"
                + (f", holdout {best_holdout:.0%}" if best_holdout is not None else ""))
        else:
            # Red-team finding #8 (iter 30): same safety check as the
            # L1-fail branch above — a failed revert means the mutation
            # is still in the working tree and subsequent iterations
            # would build on corrupt state. Abort the loop cleanly
            # instead of pretending the revert succeeded.
            revert = git_revert_last(skill_path)
            if not revert.get("success"):
                msg = (
                    f"Gate decision={decision} at iter {iteration}; "
                    f"git revert ALSO failed ({revert.get('output', 'no output')}). "
                    f"Working tree is in an undefined state. Aborting loop."
                )
                log(f"  ABORT: {msg}")
                phase_7_log(workspace, iteration, commit["commit_hash"],
                            new_rate * 100, delta * 100,
                            1.0, new_eval.get("tokens", 0), "fail", "crash",
                            current_layer, msg)
                return {"success": False, "error": msg,
                        "baseline_rate": baseline_rate, "best_rate": best_rate}
            log(f"  {decision.upper()} — reverted")

        # Phase 7: Log (writes results.tsv + experiments.jsonl +
        # iteration-E{N}/meta.json + iteration-E{N}/cases/case_{id}.json
        # — the full paper §2 filesystem layout for next-iter Phase 1
        # grep/cat access)
        elapsed = time.time() - t0
        phase_7_log(workspace, iteration, commit["commit_hash"],
                    new_rate * 100, delta * 100,
                    new_eval.get("trigger_f1", 1.0), new_eval.get("tokens", 0),
                    "pass", decision,
                    current_layer, result_23["description"],
                    experiment={
                        "iteration": iteration,
                        "mutation_type": result_23["mutation_type"],
                        "mutation_layer": current_layer,
                        "intent": result_23["description"],
                        "status": decision,
                        "elapsed_seconds": round(elapsed, 1),
                        "tokens": new_eval.get("tokens", 0),
                        "duration": new_eval.get("duration", 0.0),
                        "diagnosis": result_23.get("diagnosis", ""),
                    },
                    eval_result=new_eval,
                    split="dev")
        log(f"  Logged ({elapsed:.1f}s)")

        # Phase 8: Loop control
        ctrl = phase_8_loop_control(workspace, max_iterations)
        log(f"Phase 8: {ctrl['reason']}")
        if not ctrl["continue"]:
            break
        if ctrl.get("promote_layer"):
            current_layer = ctrl["next_layer"]
            log(f"  PROMOTE → {current_layer}")

    # Final
    log("")
    log("=" * 60)
    log("EVOLVE COMPLETE")
    log("=" * 60)

    # Guard the final holdout eval — every other holdout call routes through
    # _eval_holdout_or_none, but this one was a bare full_eval indexed with
    # holdout["pass_rate"], so a non-local evaluator that raises or omits
    # pass_rate on an empty holdout split crashed the whole run AFTER all
    # iterations had already succeeded. Fall back to the in-memory
    # best_holdout (no recompute needed) on failure / empty split.
    _fallback_rate = best_holdout if best_holdout is not None else 0.0
    try:
        holdout = evaluator.full_eval(skill_path, gt_path, split="holdout")
        if not holdout or holdout.get("total_assertions", 0) == 0:
            holdout = {"pass_rate": _fallback_rate,
                       "total_assertions": 0, "cases": []}
    except Exception as exc:
        log(f"Final holdout eval failed (non-fatal): {exc}")
        holdout = {"pass_rate": _fallback_rate,
                   "total_assertions": 0, "cases": []}
    final_rows = parse_results_tsv(workspace)
    final_summary = calculate_summary(final_rows)

    log(f"Baseline: {baseline_rate:.0%} → Best: {best_rate:.0%}")
    log(f"Keeps: {final_summary['keep_count']} | Discards: {final_summary['discard_count']}")
    log(f"Holdout: {holdout['pass_rate']:.0%}")

    cleanup_best_versions(workspace, keep_n=3)

    # Build real skill outputs for eval viewer, then generate HTML
    viewer_data_dir = None
    try:
        viewer_data_dir = _prepare_viewer_data(workspace, holdout, skill_path)
    except Exception as exc:
        log(f"Viewer data preparation failed (non-fatal): {exc}")
    viewer_launched = _try_launch_eval_viewer(
        workspace, skill_path, viewer_data_dir=viewer_data_dir)
    if viewer_launched:
        log("Eval viewer launched — open the URL above to review results")

    return {
        "baseline_rate": baseline_rate,
        "best_rate": best_rate,
        "holdout_rate": holdout["pass_rate"],
        "iterations": final_summary["total_iterations"],
        "keeps": final_summary["keep_count"],
        "discards": final_summary["discard_count"],
        "viewer_launched": viewer_launched,
        "tokens_spent": tokens_spent,
        "stop_reason": stop_reason or "loop control / max iterations",
        "resumed": resume_state is not None,
    }


# ─────────────────────────────────────────────
# Main (reference CLI)
# ─────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Evolve loop orchestrator")
    parser.add_argument("skill_path", type=Path, help="Path to target skill")
    parser.add_argument("--gt", type=Path, default=None, help="Path to GT JSON")
    parser.add_argument("--max-iterations", type=int, default=20)
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--model", default=None, help="Model for LLM CLI")
    parser.add_argument("--evaluator", default=None,
                        choices=["local", "creator", "script", "pytest"],
                        help="Evaluator engine (default: auto-detect from evolve_plan.md)")
    parser.add_argument("--evaluator-script", default=None,
                        help="Path to eval script (for --evaluator script)")
    parser.add_argument("--evaluator-test-cmd", default=None,
                        help="Test command (for --evaluator pytest)")
    parser.add_argument("--run", action="store_true",
                        help="Run the full auto evolve loop")
    parser.add_argument("--resume", action="store_true",
                        help="Continue a previous run from its existing "
                             "workspace results.tsv (re-evaluate the current "
                             "best-kept tree as baseline, continue the "
                             "iteration counter + layer) instead of starting "
                             "a fresh baseline")
    parser.add_argument("--max-total-tokens", type=int, default=None,
                        help="Budget guardrail: stop once cumulative eval "
                             "tokens reach this value (default: no limit)")
    parser.add_argument("--max-wall-seconds", type=float, default=None,
                        help="Budget guardrail: stop once wall-clock since "
                             "loop start reaches this many seconds "
                             "(default: no limit)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview the first iteration's proposed "
                             "mutation without committing or gating — "
                             "Phase 0..3 run, then the working tree "
                             "is reverted and the proposal is returned")
    parser.add_argument("--info", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--cleanup-versions", action="store_true")
    parser.add_argument("--creator-path", type=Path, default=None,
                        help="Path to skill-creator installation (overrides auto-discovery)")
    parser.add_argument("--verbose", action="store_true", default=True)
    args = parser.parse_args()

    # Set creator path override via env var (picked up by require_creator())
    if args.creator_path:
        os.environ["SKILL_CREATOR_PATH"] = str(args.creator_path.resolve())

    ws = args.workspace or find_workspace(args.skill_path)

    if args.info:
        # Evaluator registry was removed in iter 19 in favor of lazy
        # imports. Enumerate the known backend names here instead of
        # poking into evaluators.py internals.
        from evaluators import EVALUATOR_NAMES
        evaluators_info = {name: name.capitalize() + "Evaluator"
                           for name in EVALUATOR_NAMES}
        print(json.dumps({
            "phases": {
                "phase_0": "Setup (auto)", "phase_1": "Review (auto)",
                "phase_2_3": "Ideate+Modify (LLM)", "phase_4": "Commit (auto)",
                "phase_5": "Verify (pluggable evaluator)", "phase_6": "Gate (auto)",
                "phase_7": "Log (auto)", "phase_8": "Loop control (auto)",
            },
            "evaluators": evaluators_info,
        }, indent=2))
        return

    if args.cleanup:
        print(json.dumps({"cleaned": cleanup_eval_outputs(ws)}, indent=2))
        return

    if args.cleanup_versions:
        print(json.dumps({"cleaned": cleanup_best_versions(ws)}, indent=2))
        return

    if not args.gt:
        # Auto-discover GT data
        candidates = [
            ws / "evals" / "evals.json",
            args.skill_path / "evals.json",
            args.skill_path.parent / "evals.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                args.gt = candidate
                print(f"Auto-discovered GT data: {candidate}", file=sys.stderr)
                break
        if not args.gt:
            # Auto-construct GT using LLM to analyze the skill
            gt_target = ws / "evals" / "evals.json"
            gt_target.parent.mkdir(parents=True, exist_ok=True)
            print("No GT data found. Auto-constructing from SKILL.md...",
                  file=sys.stderr)
            gt_result = auto_construct_gt(args.skill_path, gt_target,
                                          model=args.model)
            if gt_result:
                args.gt = gt_target
                print(f"Generated {gt_result['count']} test cases → {gt_target}",
                      file=sys.stderr)
            else:
                print("Error: GT auto-construction failed. Provide --gt manually.",
                      file=sys.stderr)
                sys.exit(1)

    # Build evaluator from CLI args or evolve_plan.md
    eval_config = {}
    if args.evaluator:
        eval_config["evaluator"] = args.evaluator
    if args.evaluator_script:
        eval_config["evaluator_script"] = args.evaluator_script
    if args.evaluator_test_cmd:
        eval_config["evaluator_test_cmd"] = args.evaluator_test_cmd
    if args.model:
        eval_config["model"] = args.model

    evaluator_instance = None
    if eval_config.get("evaluator"):
        evaluator_instance = get_evaluator(eval_config)

    # Verify creator is available before doing any real work
    try:
        creator = require_creator()
        print(f"skill-creator found: {creator}", file=sys.stderr)
    except CreatorNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    if args.run or args.dry_run:
        # THE REAL LOOP (or dry-run preview)
        result = run_evolve_loop(
            args.skill_path, args.gt, ws,
            max_iterations=args.max_iterations,
            model=args.model, verbose=args.verbose,
            evaluator=evaluator_instance,
            dry_run=args.dry_run,
            resume=args.resume,
            max_total_tokens=args.max_total_tokens,
            max_wall_seconds=args.max_wall_seconds,
        )
        print(json.dumps(result, indent=2, default=str))
    else:
        # Setup only
        setup = phase_0_setup(args.skill_path, args.gt, ws)
        print(json.dumps(setup, indent=2))
        print("\nTo run the full loop, add --run:", file=sys.stderr)
        print(f"  python evolve_loop.py {args.skill_path} --gt {args.gt} --run",
              file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        sys.exit(130)
    except FileNotFoundError as e:
        print(f"Error: File not found — {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in GT data — {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Run with PYTHONTRACEBACK=1 for full traceback.", file=sys.stderr)
        if os.environ.get("PYTHONTRACEBACK"):
            raise
        sys.exit(1)
