import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTENDS = ROOT / "frontends"
if str(FRONTENDS) not in sys.path:
    sys.path.insert(0, str(FRONTENDS))

_TEST_GA_ROOT = tempfile.TemporaryDirectory()
_TEST_GA_PATH = Path(_TEST_GA_ROOT.name)
(_TEST_GA_PATH / "agentmain.py").touch()
_old_ga_root = os.environ.get("GA_ROOT")
_old_argv = sys.argv[:]
os.environ["GA_ROOT"] = str(_TEST_GA_PATH)
sys.argv = [sys.argv[0]]
try:
    spec = importlib.util.spec_from_file_location(
        "desktop_bridge_session_id_test", FRONTENDS / "desktop_bridge.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("failed to load desktop_bridge.py")
    bridge = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bridge
    spec.loader.exec_module(bridge)
finally:
    sys.argv = _old_argv
    if _old_ga_root is None:
        os.environ.pop("GA_ROOT", None)
    else:
        os.environ["GA_ROOT"] = _old_ga_root


class DesktopSessionIdPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.manager = bridge.AgentManager()
        self.manager.sessions.clear()
        self.manager.active_session_id = None

    @staticmethod
    def _write_session(source: Path, sid: str):
        sessions = source / "temp" / "desktop_sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        (sessions / "import.json").write_text(
            json.dumps({"id": sid, "messages": [], "msg_seq": 0}),
            encoding="utf-8",
        )

    def test_import_rejects_traversal_id_without_writing_outside_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            self._write_session(source, "../../escape")
            escaped = _TEST_GA_PATH / "escape.json"

            result = self.manager.import_sessions(str(source))

        self.assertEqual(result["sessionsAdded"], 0)
        self.assertEqual(result["sessionsSkipped"], 1)
        self.assertNotIn("../../escape", self.manager.sessions)
        self.assertFalse(escaped.exists())

    def test_import_keeps_valid_session_ids(self):
        sid = "sess-safe123"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            self._write_session(source, sid)

            result = self.manager.import_sessions(str(source))

        self.assertEqual(result["sessionsAdded"], 1)
        self.assertEqual(result["sessionsSkipped"], 0)
        self.assertIn(sid, self.manager.sessions)
        self.assertTrue((self.manager._sessions_dir / f"{sid}.json").is_file())


if __name__ == "__main__":
    unittest.main()
