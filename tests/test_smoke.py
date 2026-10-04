"""Offline contract checks; no requests to GigaChat and no real secrets."""
import contextlib
import io
import json
import os
import ssl
import unittest
import urllib.error
import uuid
from unittest.mock import patch

import test_gigachat as app


class SmokeTests(unittest.TestCase):
    def test_oauth_then_chat_and_no_secret_output(self):
        requests = []

        def fake_open(request, **kwargs):
            requests.append(request)
            self.assertEqual(kwargs["context"].verify_mode, ssl.CERT_REQUIRED)
            response = ({"access_token": "private-token"} if len(requests) == 1
                        else {"choices": [{"message": {"content": "Работает"}}]})
            return io.BytesIO(json.dumps(response).encode())

        output = io.StringIO()
        with patch.dict(os.environ, {"GIGACHAT_AUTH_KEY": "private-key"}, clear=True), \
                patch.object(app, "load_env"), \
                patch.object(app.urllib.request, "urlopen", side_effect=fake_open), \
                contextlib.redirect_stdout(output):
            app.run()
        self.assertEqual(requests[0].get_header("Authorization"), "Basic private-key")
        self.assertEqual(uuid.UUID(requests[0].get_header("Rquid")).version, 4)
        self.assertEqual(requests[0].data, b"scope=GIGACHAT_API_PERS")
        self.assertEqual(requests[1].get_header("Authorization"), "Bearer private-token")
        self.assertEqual(json.loads(requests[1].data)["messages"][0]["content"], app.PROMPT)
        self.assertIn("Ответ модели: Работает", output.getvalue())
        self.assertNotIn("private-key", output.getvalue())
        self.assertNotIn("private-token", output.getvalue())

    def test_http_error_does_not_expose_response(self):
        error = urllib.error.HTTPError(app.AUTH_URL, 401, "private-secret", {},
                                       io.BytesIO(b"private-token"))
        with patch.object(app.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "HTTP 401") as caught:
                app.post_json(app.AUTH_URL, {}, b"", ssl.create_default_context())
        self.assertNotIn("private", str(caught.exception))

    def test_tls_failure_has_actionable_message(self):
        error = urllib.error.URLError(ssl.SSLCertVerificationError("private-detail"))
        with patch.object(app.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "GIGACHAT_CA_BUNDLE"):
                app.post_json(app.AUTH_URL, {}, b"", ssl.create_default_context())

    def test_missing_access_token_stops_before_chat(self):
        with patch.object(app, "load_env"), patch.object(app, "credentials", return_value="fake"), \
                patch.object(app, "post_json", return_value={}) as post:
            with self.assertRaisesRegex(RuntimeError, "access_token"):
                app.run()
            self.assertEqual(post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
