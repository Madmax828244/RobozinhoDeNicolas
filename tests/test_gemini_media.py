"""Formato das requisições/respostas do Gemini (rede simulada)."""
import base64
import struct
import unittest
from unittest import mock

from nicolas import gemini_media as gm
from nicolas.config import Config
from nicolas.net import NetError

CFG = Config(ai_provider="gemini", ai_model="m-text", ai_api_key="K", ai_image_model="m-img", ai_tts_model="m-tts")


class GeminiMediaTests(unittest.TestCase):
    def test_generate_sends_media_tools_and_parses_calls(self):
        resp = {"candidates": [{"content": {"parts": [
            {"text": "ok"}, {"functionCall": {"name": "gerar_imagem", "args": {"descricao": "gato"}}}]}}]}
        with mock.patch.object(gm, "request_json", return_value=resp) as rj:
            out = gm.generate(CFG, "oi", "sys", media=[{"mime": "audio/ogg; codecs=opus", "data": "QUJD"}])
        url, kw = rj.call_args.args[0], rj.call_args.kwargs
        self.assertTrue(url.endswith("/models/m-text:generateContent"))
        self.assertEqual(kw["headers"], {"x-goog-api-key": "K"})
        parts = kw["data"]["contents"][0]["parts"]
        self.assertEqual(parts[1]["inlineData"], {"mimeType": "audio/ogg", "data": "QUJD"})
        self.assertEqual(kw["data"]["tools"][0]["functionDeclarations"][0]["name"], "gerar_imagem")
        self.assertEqual(out, {"text": "ok", "calls": [{"name": "gerar_imagem", "args": {"descricao": "gato"}}]})

    def test_generate_rejects_empty_and_malformed(self):
        for bad in ({}, {"candidates": []}, {"candidates": [{"content": {"parts": [{"text": " "}]}}]}):
            with mock.patch.object(gm, "request_json", return_value=bad), self.assertRaises(NetError):
                gm.generate(CFG, "oi", "sys")

    def test_make_image(self):
        resp = {"candidates": [{"content": {"parts": [{"text": "x"}, {"inlineData": {"mimeType": "image/png", "data": "SU1H"}}]}}]}
        with mock.patch.object(gm, "request_json", return_value=resp) as rj:
            self.assertEqual(gm.make_image(CFG, "um gato"), ("image/png", "SU1H"))
        self.assertEqual(rj.call_args.kwargs["data"]["generationConfig"]["responseModalities"], ["TEXT", "IMAGE"])
        with mock.patch.object(gm, "request_json", return_value={"candidates": [{"content": {"parts": [{"text": "só texto"}]}}]}):
            with self.assertRaises(NetError):
                gm.make_image(CFG, "x")

    def test_speak_falls_back_to_wav_without_ffmpeg(self):
        pcm = struct.pack("<8h", *range(8))
        resp = {"candidates": [{"content": {"parts": [{"inlineData": {
            "mimeType": "audio/L16;codec=pcm;rate=24000", "data": base64.b64encode(pcm).decode()}}]}}]}
        with mock.patch.object(gm, "request_json", return_value=resp) as rj, mock.patch.object(gm.shutil, "which", return_value=None):
            v = gm.speak(CFG, "olá")
        self.assertEqual((v["mimetype"], v["ptt"]), ("audio/wav", False))
        self.assertTrue(v["data"].startswith(b"RIFF"))
        body = rj.call_args.kwargs["data"]
        self.assertEqual(body["generationConfig"]["responseModalities"], ["AUDIO"])
        self.assertTrue(rj.call_args.args[0].endswith("m-tts:generateContent"))

    def test_speak_uses_opus_when_ffmpeg_works(self):
        pcm = b"\x00\x00" * 100
        resp = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;rate=24000",
                                                                       "data": base64.b64encode(pcm).decode()}}]}}]}
        done = mock.Mock(returncode=0, stdout=b"OggS-data")
        with mock.patch.object(gm, "request_json", return_value=resp), mock.patch.object(gm.shutil, "which", return_value="/x/ffmpeg"), \
             mock.patch.object(gm.subprocess, "run", return_value=done):
            v = gm.speak(CFG, "olá")
        self.assertEqual((v["data"], v["mimetype"], v["ptt"]), (b"OggS-data", "audio/ogg; codecs=opus", True))


if __name__ == "__main__":
    unittest.main()


class GeminiTextTests(unittest.TestCase):
    def test_empty_candidate_reports_reason_and_limit_has_headroom(self):
        from nicolas.ai_client import ask, THINKING_HEADROOM
        empty = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"role": "model"}}]}
        with mock.patch("nicolas.ai_client.request_json", return_value=empty) as rj:
            with self.assertRaises(NetError) as cm:
                ask(CFG, "oi", max_tokens=30)
        self.assertIn("MAX_TOKENS", str(cm.exception))
        self.assertEqual(rj.call_args.kwargs["data"]["generationConfig"]["maxOutputTokens"], 30 + THINKING_HEADROOM)
        blocked = {"promptFeedback": {"blockReason": "SAFETY"}}
        with mock.patch("nicolas.ai_client.request_json", return_value=blocked):
            with self.assertRaises(NetError) as cm:
                ask(CFG, "oi")
        self.assertIn("SAFETY", str(cm.exception))
