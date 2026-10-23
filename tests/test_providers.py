import base64
import unittest
from unittest import mock

from nicolas.ai_client import ask
from nicolas.config import Config
from nicolas.net import NetError
from nicolas.providers import detect_provider
from nicolas import stt

KEY = "gsk_" + "x" * 40


def cfg(**k):
    base = dict(ai_provider="groq", ai_api_key=KEY)
    base.update(k)
    return Config(**base)


OK = {"choices": [{"message": {"content": "oi"}}]}


class ProviderTests(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(detect_provider(KEY), "groq")
        self.assertEqual(detect_provider("AIzaSy" + "a" * 30), "gemini")
        self.assertEqual(detect_provider("sk-ant-abc"), "anthropic")
        self.assertEqual(detect_provider("xyz"), "")

    def test_groq_defaults_url_and_model(self):
        c = cfg()
        self.assertTrue(c.ai_configured)  # modelo vem do padrão do provedor
        with mock.patch("nicolas.ai_client.request_json", return_value=OK) as rj:
            self.assertEqual(ask(c, "oi"), "oi")
        url = rj.call_args[0][0]
        self.assertEqual(url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(rj.call_args[1]["headers"]["Authorization"], f"Bearer {KEY}")

    def test_fallback_on_429_and_not_on_400(self):
        c = cfg(ai_fallback_provider="gemini", ai_fallback_api_key="AIza" + "b" * 30)
        gem = {"candidates": [{"content": {"parts": [{"text": "da reserva"}]}}]}
        calls = []

        def fake(url, **k):
            calls.append(url)
            if "groq" in url:
                raise NetError("o serviço respondeu com erro HTTP 429", 429)
            return gem
        with mock.patch("nicolas.ai_client.request_json", side_effect=fake):
            self.assertEqual(ask(c, "oi"), "da reserva")
        self.assertEqual(len(calls), 2)
        with mock.patch("nicolas.ai_client.request_json", side_effect=NetError("HTTP 400", 400)) as rj:
            with self.assertRaises(NetError):
                ask(c, "oi")
        self.assertEqual(rj.call_count, 1)

    def test_no_fallback_without_key(self):
        self.assertIsNone(cfg(ai_fallback_provider="gemini").fallback())

    def test_transcribe(self):
        with mock.patch("nicolas.stt.post_multipart", return_value={"text": " olá mundo "}) as pm:
            out = stt.transcribe(cfg(), base64.b64encode(b"abc").decode(), "audio/ogg; codecs=opus")
        self.assertEqual(out, "olá mundo")
        self.assertTrue(pm.call_args[0][0].endswith("/audio/transcriptions"))
        self.assertEqual(pm.call_args[1]["fields"]["model"], "whisper-large-v3-turbo")
        with self.assertRaises(NetError):
            stt.transcribe(cfg(ai_provider="anthropic"), "AA==")


if __name__ == "__main__":
    unittest.main()


class ModelListTests(unittest.TestCase):
    def test_list_and_pick_groq(self):
        from nicolas.ai_client import list_models, pick_model
        data = {"data": [{"id": "whisper-large-v3"}, {"id": "openai/gpt-oss-120b"}, {"id": "llama-guard-4"},
                         {"id": "llama-3.1-8b-instant"}]}
        with mock.patch("nicolas.ai_client.request_json", return_value=data) as rj:
            ids = list_models(cfg())
        self.assertEqual(rj.call_args[0][0], "https://api.groq.com/openai/v1/models")
        self.assertEqual(ids, ["llama-3.1-8b-instant", "openai/gpt-oss-120b"])
        self.assertEqual(pick_model(ids), "openai/gpt-oss-120b")

    def test_list_gemini_only_generate_content(self):
        from nicolas.ai_client import list_models
        data = {"models": [{"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                           {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]}]}
        with mock.patch("nicolas.ai_client.request_json", return_value=data):
            self.assertEqual(list_models(cfg(ai_provider="gemini")), ["gemini-2.5-flash"])

    def test_retry_once_on_503(self):
        n = []

        def fake(url, **k):
            n.append(1)
            if len(n) == 1:
                raise NetError("HTTP 503", 503)
            return OK
        with mock.patch("nicolas.ai_client.request_json", side_effect=fake), mock.patch("nicolas.ai_client.time.sleep"):
            self.assertEqual(ask(cfg(), "oi"), "oi")
        self.assertEqual(len(n), 2)

    def test_local_provider_works_without_api_key(self):
        c = Config(ai_provider="ollama", ai_model="llama3.2:3b")
        self.assertTrue(c.ai_configured)
        with mock.patch("nicolas.ai_client.request_json", return_value=OK) as rj:
            self.assertEqual(ask(c, "oi"), "oi")
        self.assertEqual(rj.call_args.args[0], "http://127.0.0.1:11434/v1/chat/completions")
        self.assertNotIn("Authorization", rj.call_args.kwargs["headers"])

    def test_custom_compatible_api_needs_url_but_not_key(self):
        self.assertFalse(Config(ai_provider="openai-compatible", ai_model="m").ai_configured)
        c = Config(ai_provider="openai-compatible", ai_model="m",
                   ai_base_url="http://127.0.0.1:11434/v1")
        self.assertTrue(c.ai_configured)

    def test_private_http_api_needs_explicit_opt_in(self):
        from nicolas.net import request_json
        with self.assertRaises(NetError):
            request_json("http://192.168.1.22:12434/engines/v1/models")
        with mock.patch("nicolas.net.urllib.request.urlopen") as urlopen:
            resp = mock.MagicMock()
            resp.read.return_value = b'{"data": []}'
            resp.__enter__.return_value = resp
            urlopen.return_value = resp
            self.assertEqual(request_json("http://192.168.1.22:12434/engines/v1/models",
                                          allow_insecure_private=True), {"data": []})
