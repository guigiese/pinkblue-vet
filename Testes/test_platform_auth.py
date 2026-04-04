import unittest

from fastapi.testclient import TestClient

from pb_platform.settings import settings
from web.app import app


class PlatformAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.state.disable_auth = False
        cls.client = TestClient(app)

    def test_login_page_renders_platform_copy(self):
        response = self.client.get("/login")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Autenticação da plataforma", response.text)
        self.assertIn("Use seu e-mail e senha para entrar", response.text)

    def test_unauthenticated_module_access_redirects_to_login(self):
        response = self.client.get("/labmonitor/exames", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertIn("/login?next=/labmonitor/exames", response.headers["location"])

    def test_master_login_unlocks_home_and_admin(self):
        login_response = self.client.post(
            "/login",
            data={
                "email": settings.master_email,
                "password": settings.master_password,
                "next": "/",
            },
            follow_redirects=False,
        )

        self.assertEqual(login_response.status_code, 303)
        self.assertEqual(login_response.headers["location"], "/")

        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn("Biblioteca de módulos", home.text)
        self.assertIn("Lab Monitor", home.text)

        admin = self.client.get("/admin/usuarios")
        self.assertEqual(admin.status_code, 200)
        self.assertIn("Usuários da plataforma", admin.text)
        self.assertIn("Permissões por perfil", admin.text)

        self.client.get("/logout")


if __name__ == "__main__":
    unittest.main()
