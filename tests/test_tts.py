"""Voz independente do modelo de texto (OpenRouter/Groq + espeak/OpenAI/Gemini). Nenhuma rede/áudio real."""
import base64
import unittest
from unittest import mock

from nicolas import tts
from nicolas.config import Config
from nicolas.net import NetError

from .helpers import CHAT, MEMBER, make_bot, prime, say

OR = dict(ai_provider="openrouter", ai_model="minimax/minimax-m2:free", ai_api_key="CHAVE-SECRETA-DE-TESTE")


def fake_ask(cfg, prompt, history=(), system="", max_tokens=700):
    fake_ask.calls.append({"prompt": prompt, "system": system})
    return "Oi pessoal, tudo bem com vocês?"


class EngineChoiceTests(unittest.TestCase):
    def test_auto_picks_local_when_installed_and_none_otherwise(self):
        c = Config(**OR)
        with mock.patch("nicolas.tts._local_bin", return_value="/usr/bin/espeak-ng"):
            self.assertEqual(tts.engine(c), "local")
        with mock.patch("nicolas.tts._local_bin", return_value=None):
            self.assertIsNone(tts.engine(c))
            self.assertFalse(tts.available(c))

    def test_gemini_text_provider_uses_gemini_voice(self):
        c = Config(ai_provider="gemini", ai_model="m", ai_api_key="K" * 30)
        self.assertEqual(tts.engine(c), "gemini")

    def test_explicit_engines_need_their_keys(self):
        self.assertIsNone(tts.engine(Config(**OR, ai_tts_engine="openai")))
        self.assertEqual(tts.engine(Config(**OR, ai_tts_engine="openai", ai_tts_api_key="K" * 30)), "openai")
        self.assertIsNone(tts.engine(Config(**OR, ai_tts_engine="gemini")))
        self.assertEqual(tts.engine(Config(**OR, ai_tts_engine="gemini", ai_tts_api_key="K" * 30)), "gemini")

    def test_openai_compatible_speech_request(self):
        c = Config(**OR, ai_tts_engine="openai", ai_tts_api_key="K" * 30)
        with mock.patch("nicolas.tts.request_bytes", return_value=b"OggS" + b"x" * 200) as rb:
            out = tts.speak(c, "olá")
        self.assertEqual(rb.call_args[0][0], "https://api.openai.com/v1/audio/speech")
        self.assertEqual(rb.call_args[1]["data"]["input"], "olá")
        self.assertTrue(out["ptt"])
        self.assertEqual(out["mimetype"], "audio/ogg; codecs=opus")

    def test_failure_falls_back_to_local_voice(self):
        c = Config(**OR, ai_tts_engine="openai", ai_tts_api_key="K" * 30)
        with mock.patch("nicolas.tts.request_bytes", side_effect=NetError("HTTP 500", 500)), \
             mock.patch("nicolas.tts._local_bin", return_value="/x/espeak-ng"), \
             mock.patch("nicolas.tts.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout=b"RIFF" + b"w" * 500)
            with mock.patch("nicolas.tts._to_opus_from_file", return_value=b"OggS" + b"o" * 50):
                out = tts.speak(c, "olá")
        self.assertEqual(out["data"][:4], b"OggS")

    def test_local_voice_without_ffmpeg_returns_wav_file(self):
        c = Config(**OR)
        with mock.patch("nicolas.tts._local_bin", return_value="/x/espeak-ng"), \
             mock.patch("nicolas.tts.subprocess.run", return_value=mock.Mock(returncode=0, stdout=b"RIFF" + b"w" * 500)), \
             mock.patch("nicolas.tts._to_opus_from_file", return_value=None):
            out = tts.speak(c, "olá")
        self.assertFalse(out["ptt"])
        self.assertEqual(out["mimetype"], "audio/wav")


class OpenRouterAudioRequestTests(unittest.TestCase):
    def setUp(self):
        fake_ask.calls = []
        p = mock.patch("nicolas.esperto.ask", fake_ask)
        p.start()
        self.addCleanup(p.stop)
        self.bot, self.clock = make_bot(**OR)
        prime(self.bot)
        self.bot.db.set_group(CHAT, esperto=True)
        self.clock.advance(60)

    def test_audio_request_returns_a_voice_message_not_text(self):
        v = {"data": b"OggS" + b"v" * 100, "mimetype": "audio/ogg; codecs=opus", "ptt": True}
        with mock.patch("nicolas.tts._local_bin", return_value="/x/espeak-ng"), \
             mock.patch("nicolas.esperto.tts.speak", return_value=v):
            out = say(self.bot, "cria um áudio falando oi pro grupo", sender=MEMBER)
        audio = [r for r in out if r.audio_base64]
        self.assertEqual(len(audio), 1)
        self.assertEqual(base64.b64decode(audio[0].audio_base64), v["data"])
        self.assertTrue(audio[0].ptt)
        # o modelo de texto foi instruído a escrever só o que será falado, e não a falar de "integração"
        self.assertIn("ÁUDIO", fake_ask.calls[-1]["prompt"])
        self.assertNotIn("gerar_imagem", fake_ask.calls[-1]["system"])

    def test_voice_failure_falls_back_to_text(self):
        with mock.patch("nicolas.tts._local_bin", return_value="/x/espeak-ng"), \
             mock.patch("nicolas.esperto.tts.speak", side_effect=NetError("falhou")):
            out = say(self.bot, "manda um áudio dizendo bom dia", sender=MEMBER)
        self.assertIn("Não consegui gerar o áudio", " ".join(r.text for r in out))

    def test_variants_of_the_audio_request_are_detected(self):
        from nicolas.esperto import _requests_audio
        for t in ("cria um áudio", "me manda um audio dizendo oi", "gera uma mensagem de voz", "fala isso em voz alta",
                  "responde em áudio", "quero ouvir você"):
            self.assertTrue(_requests_audio(t), t)
        for t in ("o áudio ficou ruim", "qual a capital da França?"):
            self.assertFalse(_requests_audio(t), t)

    def test_image_request_is_honest_on_text_provider(self):
        out = " ".join(r.text for r in say(self.bot, "cria uma imagem de um gato", sender=MEMBER))
        self.assertIn("Imagens só funcionam com o provedor Gemini", out)


if __name__ == "__main__":
    unittest.main()


class ElevenLabsTests(unittest.TestCase):
    def cfg(self, **k):
        return Config(**OR, ai_tts_engine="elevenlabs", ai_tts_api_key="K" * 30, ai_tts_voice_id="VOZ123", **k)

    def test_needs_key_and_voice_id(self):
        self.assertIsNone(tts.engine(Config(**OR, ai_tts_engine="elevenlabs", ai_tts_api_key="K" * 30)))
        self.assertEqual(tts.engine(self.cfg()), "elevenlabs")

    def test_request_and_conversion_to_voice_message(self):
        with mock.patch("nicolas.tts.request_bytes", return_value=b"ID3" + b"m" * 200) as rb, \
             mock.patch("nicolas.tts._to_opus_from_file", return_value=b"OggS" + b"o" * 50):
            out = tts.speak(self.cfg(), "olá mundo")
        url = rb.call_args[0][0]
        self.assertTrue(url.startswith("https://api.elevenlabs.io/v1/text-to-speech/VOZ123"))
        self.assertEqual(rb.call_args[1]["headers"]["xi-api-key"], "K" * 30)
        self.assertEqual(rb.call_args[1]["data"], {"text": "olá mundo", "model_id": "eleven_multilingual_v2"})
        self.assertTrue(out["ptt"])

    def test_without_ffmpeg_sends_mp3_file(self):
        with mock.patch("nicolas.tts.request_bytes", return_value=b"ID3" + b"m" * 200), \
             mock.patch("nicolas.tts._to_opus_from_file", return_value=None):
            out = tts.speak(self.cfg(), "oi")
        self.assertEqual((out["mimetype"], out["ptt"]), ("audio/mpeg", False))
