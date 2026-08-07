import importlib.util
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
FRONTENDS = ROOT / "frontends"
_TEST_GA_ROOT = tempfile.TemporaryDirectory()
unittest.addModuleCleanup(_TEST_GA_ROOT.cleanup)
_TEST_GA_PATH = Path(_TEST_GA_ROOT.name)
(_TEST_GA_PATH / "agentmain.py").touch()


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"failed to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load_module("plan_state", FRONTENDS / "plan_state.py")
_old_ga_root = os.environ.get("GA_ROOT")
_old_argv = sys.argv[:]
os.environ["GA_ROOT"] = str(_TEST_GA_PATH)
sys.argv = [sys.argv[0]]
try:
    bridge = _load_module("desktop_bridge_persistence_test", FRONTENDS / "desktop_bridge.py")
finally:
    sys.argv = _old_argv
    if _old_ga_root is None:
        os.environ.pop("GA_ROOT", None)
    else:
        os.environ["GA_ROOT"] = _old_ga_root


class DesktopSessionPersistenceTests(unittest.TestCase):
    def setUp(self):
        sessions_dir = _TEST_GA_PATH / "temp" / "desktop_sessions"
        if sessions_dir.is_dir():
            for path in sessions_dir.iterdir():
                if path.is_file():
                    path.unlink()
        self.manager = bridge.AgentManager()
        self.manager.sessions.clear()
        self.manager.active_session_id = None

    def _registered_session(self, sid="sess-race123"):
        sess = bridge.Session(id=sid, cwd=str(_TEST_GA_PATH))
        with self.manager.lock:
            self.manager.sessions[sid] = sess
        return sess

    def test_same_session_temp_writes_do_not_overlap(self):
        sess = self._registered_session()
        original_write_text = Path.write_text
        guard = threading.Lock()
        first_entered = threading.Event()
        second_entered = threading.Event()
        active = 0
        overlap = False

        def probed_write_text(path, *args, **kwargs):
            nonlocal active, overlap
            if path.name != f"{sess.id}.json.tmp":
                return original_write_text(path, *args, **kwargs)
            with guard:
                active += 1
                slot = active
                if active > 1:
                    overlap = True
                if slot == 1:
                    first_entered.set()
                else:
                    second_entered.set()
            if slot == 1:
                second_entered.wait(0.3)
            else:
                first_entered.wait(0.3)
            try:
                return original_write_text(path, *args, **kwargs)
            finally:
                with guard:
                    active -= 1

        with mock.patch.object(Path, "write_text", autospec=True, side_effect=probed_write_text):
            threads = [threading.Thread(target=self.manager._persist_session, args=(sess,)) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=3)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertFalse(overlap, "same-session temp writes overlapped")

    def test_late_persist_does_not_recreate_deleted_session_file(self):
        sess = self._registered_session("sess-deleted123")
        self.manager._persist_session(sess)
        session_file = self.manager._session_file(sess.id)
        self.assertTrue(session_file.is_file())

        self.manager.delete_session(sess.id)
        self.assertFalse(session_file.exists())

        self.manager._persist_session(sess)

        self.assertFalse(session_file.exists())
        self.assertNotIn(sess.id, self.manager.sessions)


if __name__ == "__main__":
    unittest.main()
