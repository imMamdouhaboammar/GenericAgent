import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTMAIN = ROOT / "agentmain.py"


def run_agentmain(*args):
    env = os.environ.copy()
    env["GA_LANG"] = "en"
    return subprocess.run(
        [sys.executable, str(AGENTMAIN), *args],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        env=env,
    )


class AgentMainCliArgumentTests(unittest.TestCase):
    def test_unknown_args_without_reflect_fail_fast(self):
        result = run_agentmain("--goal", "dummy-goal.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments: --goal dummy-goal.json", result.stderr)
        self.assertNotIn("EOFError", result.stderr)

    def test_reflect_extras_require_complete_key_value_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "reflect_exit.py"
            script.write_text("def check(): return '/exit'\n", encoding="utf-8")
            for extras in (("--name",), ("--name", "--other")):
                with self.subTest(extras=extras):
                    result = run_agentmain("--reflect", str(script), *extras)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("reflect extra arguments must be --key value pairs", result.stderr)

    def test_reflect_key_value_extras_remain_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "reflect_exit.py"
            script.write_text(
                "def init(args): print('INIT_NAME=' + str(args.get('name')))\n"
                "def check(): return '/exit'\n",
                encoding="utf-8",
            )
            result = run_agentmain("--reflect", str(script), "--name", "hive-master")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("INIT_NAME=hive-master", result.stdout)
        self.assertIn("[Reflect] loaded", result.stdout)


if __name__ == "__main__":
    unittest.main()
