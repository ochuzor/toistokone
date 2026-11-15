import unittest

from backend.app.main import app, health


class HealthEndpointTests(unittest.TestCase):
    def test_health_endpoint_returns_ok(self) -> None:
        self.assertEqual(health(), {"status": "ok"})

    def test_health_route_is_registered(self) -> None:
        routes = {(route.path, tuple(route.methods or ())) for route in app.routes}
        self.assertIn(("/api/health", ("GET",)), routes)
