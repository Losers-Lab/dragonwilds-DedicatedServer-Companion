import os
import unittest

try:
    from app import app
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False


class TestUserInterface(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.templates_dir = os.path.join(self.base_dir, 'templates')
        self.static_dir = os.path.join(self.base_dir, 'static')

    def test_template_structure(self):
        index_path = os.path.join(self.templates_dir, 'index.html')
        self.assertTrue(os.path.exists(index_path), "templates/index.html must exist")
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('<title>Dragonwilds Companion</title>', content)
        self.assertIn('href="/static/style.css"', content)
        self.assertIn('src="/static/app.js"', content)
        self.assertIn('mobile-drawer', content)
        self.assertIn('drawer-backdrop', content)
        self.assertIn('view-overview', content)
        self.assertIn('view-map', content)
        self.assertIn('view-respawns', content)
        self.assertIn('view-farming', content)
        self.assertIn('view-items', content)
        self.assertIn('view-bosses', content)
        self.assertIn('view-players', content)
        self.assertIn('view-backups', content)
        self.assertIn('view-leaderboard', content)
        self.assertIn('view-events', content)
        self.assertIn('view-logs', content)

    def test_static_stylesheet_tokens(self):
        css_path = os.path.join(self.static_dir, 'style.css')
        self.assertTrue(os.path.exists(css_path), "static/style.css must exist")
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn('--bg-deep: #221d1a;', css)
        self.assertIn('--bg-root: #312a26;', css)
        self.assertIn('--gold-core: #ebd15f;', css)
        self.assertIn('--rune-green: #84be5b;', css)
        self.assertIn('--blood-red: #c43a2e;', css)
        self.assertIn('.mobile-drawer', css)
        self.assertIn('.mobile-topbar', css)

    def test_static_javascript_functions(self):
        js_path = os.path.join(self.static_dir, 'app.js')
        self.assertTrue(os.path.exists(js_path), "static/app.js must exist")
        with open(js_path, 'r', encoding='utf-8') as f:
            js = f.read()

        self.assertIn('function toggleDrawer()', js)
        self.assertIn('function closeDrawer()', js)
        self.assertIn('function setTab(tab)', js)
        self.assertIn('function renderDayNightDial', js)
        self.assertIn('function renderWorldMap', js)
        self.assertIn('function renderRespawns', js)
        self.assertIn('function renderFarming', js)
        self.assertIn('function renderStoredItems', js)
        self.assertIn('function renderBosses', js)

    def test_flask_endpoints_if_available(self):
        if not HAS_FLASK:
            self.skipTest("Flask not installed in test runner environment")
        client = app.test_client()
        resp = client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Dragonwilds Companion', resp.data)


if __name__ == '__main__':
    unittest.main()
