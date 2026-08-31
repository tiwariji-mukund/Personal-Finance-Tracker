from django.test import SimpleTestCase, override_settings

from apps.telegram_bot.bot import create_application


class CreateApplicationCaBundleTests(SimpleTestCase):
    def _httpx_kwargs(self, app):
        return app.bot.request._client_kwargs

    @override_settings(TELEGRAM_CA_BUNDLE='/etc/ssl/certs/ca-certificates.crt')
    def test_configured_ca_bundle_is_passed_to_the_httpx_client(self):
        app = create_application()

        self.assertEqual(self._httpx_kwargs(app).get('verify'), '/etc/ssl/certs/ca-certificates.crt')

    @override_settings(TELEGRAM_CA_BUNDLE=None)
    def test_unset_ca_bundle_preserves_default_verification(self):
        app = create_application()

        self.assertNotIn('verify', self._httpx_kwargs(app))
