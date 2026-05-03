#!/usr/bin/env python3
"""
Probe the local KMS API through /health and /stats.

Examples:
    python scripts/probe_kms_api.py
    python scripts/probe_kms_api.py --skip-stats
    python scripts/probe_kms_api.py --base-url http://127.0.0.1:49153
"""

from __future__ import annotations

import argparse
import sys

from kms_api_client import DEFAULT_BASE_URL, DEFAULT_TIMEOUT_SECONDS, build_url, print_json, request_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe the local KMS API.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"KMS API base URL. Defaults to {DEFAULT_BASE_URL}.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout in seconds. Defaults to {DEFAULT_TIMEOUT_SECONDS}.",
    )
    parser.add_argument(
        "--skip-stats",
        action="store_true",
        help="Only probe /health and skip /stats.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    health_url = build_url(args.base_url, "/health")
    stats_url = build_url(args.base_url, "/stats")

    try:
        health = request_json("GET", health_url, timeout=args.timeout)
        stats = None if args.skip_stats else request_json("GET", stats_url, timeout=args.timeout)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("kms-api probe ok")
    print_json("health", health)
    if stats is not None:
        print_json("stats", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
