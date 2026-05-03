from __future__ import annotations

import importlib.util
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CheckEnvTests(unittest.TestCase):
    def test_external_command_failures_affect_exit_code(self) -> None:
        check_env = load_module("check_env_under_test", ROOT / "scripts" / "check_env.py")
        with (
            patch.object(check_env, "check_python", return_value=True),
            patch.object(check_env, "check_module", return_value=True),
            patch.object(check_env, "check_url_md", return_value=True),
            patch.object(check_env, "check_command", side_effect=[False, True, True]),
            patch.object(check_env, "check_getnote", return_value=True),
            patch.object(check_env, "check_out_base", return_value=True),
        ):
            self.assertEqual(check_env.main(), 1)


class PodcastTranscriptTests(unittest.TestCase):
    def test_zero_note_id_is_not_treated_as_timeout(self) -> None:
        podcast = load_module(
            "podcast_under_test", ROOT / "lib" / "podcast_transcript.py"
        )

        def fake_openapi(method: str, path: str, body=None, **kwargs):
            if path.endswith("/resource/note/save"):
                return {"success": True, "data": {"tasks": [{"task_id": "task-1"}]}}
            return {"data": {"status": "success", "note_id": 0}}

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(podcast, "_check_creds", return_value=("key", "client")),
                patch.object(podcast, "_openapi_call", side_effect=fake_openapi),
                patch.object(
                    podcast,
                    "_fetch_transcript",
                    return_value={"title": "T", "content": "transcript"},
                ),
                patch.object(podcast.time, "sleep", return_value=None),
            ):
                result = podcast.fetch_podcast_transcript(
                    "https://example.com/podcast", Path(tmp), poll_interval=0, max_polls=1
                )

        self.assertTrue(result.success)
        self.assertEqual(result.note_id, "0")

    def test_first_poll_runs_before_sleep_and_uses_request_timeout(self) -> None:
        podcast = load_module(
            "podcast_under_test_2", ROOT / "lib" / "podcast_transcript.py"
        )
        calls: list[tuple[str, int | None]] = []

        def fake_openapi(method: str, path: str, body=None, **kwargs):
            calls.append((path, kwargs.get("timeout")))
            if path.endswith("/resource/note/save"):
                return {"success": True, "data": {"tasks": [{"task_id": "task-1"}]}}
            return {"data": {"status": "success", "note_id": 123}}

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(podcast, "_check_creds", return_value=("key", "client")),
                patch.object(podcast, "_openapi_call", side_effect=fake_openapi),
                patch.object(
                    podcast,
                    "_fetch_transcript",
                    return_value={"title": "T", "content": "transcript"},
                ) as fetch_transcript,
                patch.object(podcast.time, "sleep", return_value=None) as sleep,
            ):
                result = podcast.fetch_podcast_transcript(
                    "https://example.com/podcast",
                    Path(tmp),
                    poll_interval=30,
                    max_polls=1,
                    request_timeout=7,
                )

        self.assertTrue(result.success)
        sleep.assert_not_called()
        self.assertEqual([timeout for _, timeout in calls], [7, 7])
        fetch_transcript.assert_called_once_with("123", timeout=7)


class DownloadHelperTests(unittest.TestCase):
    def test_archive_captcha_keeps_detected_source_type(self) -> None:
        download = load_module("download_under_test", ROOT / "scripts" / "download.py")
        dec = download.RouteDecision(download.InputType.X_TWITTER, "https://x.com/a/status/1")

        with patch.object(
            download,
            "_handle_one",
            side_effect=download.ArchiveCaptcha("https://archive.today/captcha"),
        ):
            meta, captcha = download._dispatch(
                dec,
                Path("unused"),
                podcast_audio_only=False,
                youtube_subs_only=False,
                enable_paywall_bypass=True,
                timeout=1,
            )

        self.assertEqual(meta["source_type"], "x_twitter")
        self.assertEqual(meta["strategy_used"], "archive_captcha")
        self.assertEqual(captcha, "https://archive.today/captcha")

    def test_exception_meta_omits_traceback(self) -> None:
        download = load_module("download_under_test_2", ROOT / "scripts" / "download.py")
        meta = download._result_meta(
            source_type="webpage",
            input_value="https://example.com",
            title="",
            strategy_used="exception",
            files=[],
            success=False,
            error="ValueError: bad\nTraceback (most recent call last):\nsecret",
        )

        self.assertNotIn("Traceback", meta["error"])
        self.assertNotIn("secret", meta["error"])


class FetchUrlTests(unittest.TestCase):
    def test_agent_fetch_uses_pinned_scoped_package(self) -> None:
        fetch_url = importlib.import_module("lib.fetch_url")

        def fake_run(args, **kwargs):
            self.assertIn("--package", args)
            self.assertIn("@teng-lin/agent-fetch@0.1.6", args)
            self.assertIn("agent-fetch", args)
            return SimpleNamespace(returncode=1, stdout="")

        with (
            patch.object(fetch_url.shutil, "which", return_value="npx"),
            patch.object(fetch_url.subprocess, "run", side_effect=fake_run),
        ):
            self.assertIsNone(fetch_url._l6_agent_fetch("https://example.com", 1))

    def test_curl_get_rejects_large_content_length(self) -> None:
        fetch_url = importlib.import_module("lib.fetch_url")

        class FakeResponse:
            headers = {"Content-Length": str(fetch_url.MAX_CURL_RESPONSE_BYTES + 1)}
            encoding = "utf-8"

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def iter_content(self, chunk_size: int):
                raise AssertionError("body should not be read")

        with patch.object(fetch_url.requests, "get", return_value=FakeResponse()):
            self.assertEqual(fetch_url._curl_get("https://example.com"), "")

    def test_paywall_layer_does_not_repeat_tried_googlebot(self) -> None:
        fetch_url = importlib.import_module("lib.fetch_url")

        with (
            patch.object(fetch_url, "fetch_l1_proxy", return_value=None),
            patch.object(fetch_url, "is_googlebot_site", return_value=True),
            patch.object(fetch_url, "is_bingbot_site", return_value=False),
            patch.object(fetch_url, "is_paywall_site", return_value=True),
            patch.object(fetch_url, "_l2_googlebot", return_value=None) as googlebot,
            patch.object(
                fetch_url,
                "_l2_bingbot",
                return_value=fetch_url.FetchResult(
                    success=True, content="content", strategy_used="bingbot"
                ),
            ) as bingbot,
        ):
            result = fetch_url.fetch_url("https://example.com", timeout=1)

        self.assertTrue(result.success)
        googlebot.assert_called_once()
        bingbot.assert_called_once()


class RoutingAndOutputTests(unittest.TestCase):
    def test_webpage_canonicalization_keeps_from_and_spm(self) -> None:
        canonical = importlib.import_module("lib.url_canonical")
        router = importlib.import_module("lib.router")

        result = canonical.canonicalize(
            "https://example.com/path?b=2&from=feed&utm_source=x&spm=abc",
            router.InputType.WEBPAGE,
        )

        self.assertEqual(result, "https://example.com/path?b=2&from=feed&spm=abc")

    def test_host_detection_uses_parsed_netloc(self) -> None:
        router = importlib.import_module("lib.router")

        self.assertEqual(
            router.detect("https://notyoutube.com/watch?v=1").input_type,
            router.InputType.WEBPAGE,
        )
        self.assertEqual(
            router.detect("https://m.youtube.com/watch?v=1").input_type,
            router.InputType.YOUTUBE,
        )

    def test_safe_slug_filters_nul_dots_and_limits_utf8_bytes(self) -> None:
        output = importlib.import_module("lib.output")

        self.assertEqual(output.safe_slug("\x00..."), "untitled")
        slug = output.safe_slug("长" * 100)
        self.assertLessEqual(len(slug.encode("utf-8")), output.MAX_SLUG_BYTES)


class YoutubeDlTests(unittest.TestCase):
    def test_existing_meta_json_is_not_reported_as_downloaded_file(self) -> None:
        youtube = importlib.import_module("lib.youtube_dl")

        class FakeYdl:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, url, download=True):
                out_dir = Path(self.opts["outtmpl"]).parent
                (out_dir / "abc.info.json").write_text("{}", encoding="utf-8")
                (out_dir / "abc.mp4").write_text("video", encoding="utf-8")
                return {"id": "abc", "title": "Title"}

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            (out_dir / "meta.json").write_text("old", encoding="utf-8")
            with patch.object(youtube.yt_dlp, "YoutubeDL", FakeYdl):
                result = youtube._run_yt_dlp(
                    "https://youtu.be/abc",
                    out_dir,
                    subs_only=False,
                    audio_only=False,
                    source="youtube",
                )

        self.assertTrue(result.success)
        self.assertNotIn("meta.json", {Path(f).name for f in result.files})


if __name__ == "__main__":
    unittest.main()
