import importlib.util
import sys
import unittest
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer


ROOT = Path(__file__).resolve().parents[1]
FRONTENDS = ROOT / "frontends"
if str(FRONTENDS) not in sys.path:
    sys.path.insert(0, str(FRONTENDS))

spec = importlib.util.spec_from_file_location("desktop_bridge", FRONTENDS / "desktop_bridge.py")
bridge = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(bridge)


class DesktopBridgeOriginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        app = web.Application(middlewares=[bridge.cors_middleware])

        async def probe(request):
            return web.json_response({"ok": True})

        app.router.add_post("/probe", probe)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_cross_origin_preflight_is_rejected(self):
        response = await self.client.options(
            "/probe",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.status, 403)

    async def test_same_origin_request_is_allowed(self):
        origin = str(self.client.make_url("/")).rstrip("/")
        response = await self.client.post("/probe", headers={"Origin": origin}, json={})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)

    async def test_non_browser_request_without_origin_is_allowed(self):
        response = await self.client.post("/probe", json={})
        self.assertEqual(response.status, 200)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)


if __name__ == "__main__":
    unittest.main()
