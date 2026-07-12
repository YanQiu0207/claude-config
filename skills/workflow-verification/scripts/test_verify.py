"""Regression tests for spec drift evaluation."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import verify


class EvaluateSpecDriftTest(unittest.TestCase):
    """Verify tracked and untracked specification matching."""

    def test_untracked_tasks_file_can_be_related(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks = root / "docs" / "tasks.md"
            tasks.parent.mkdir()
            tasks.write_text("`src/tool.py`\n", encoding="utf-8")
            with mock.patch.object(
                verify,
                "_changed_files",
                return_value=([], ["src/tool.py", "docs/tasks.md"], None),
            ):
                old_cwd = Path.cwd()
                try:
                    import os

                    os.chdir(root)
                    result = verify.evaluate_spec_drift("HEAD", "")
                finally:
                    os.chdir(old_cwd)
        self.assertEqual("pass", result.status)
        self.assertEqual(["docs/tasks.md"], result.value["related_spec_files"])

    def test_unrelated_untracked_spec_still_fails(self) -> None:
        with mock.patch.object(
            verify,
            "_changed_files",
            return_value=([], ["src/tool.py", "other/spec.md"], None),
        ):
            result = verify.evaluate_spec_drift("HEAD", "")
        self.assertEqual("fail", result.status)


if __name__ == "__main__":
    unittest.main()
