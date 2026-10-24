"""Isolated speech credential, WAV validation and no-auto-send checks."""
import asyncio
import io
import os
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from fastapi import UploadFile
from starlette.datastructures import Headers

from teamspace import speech_input as asr
from teamspace.store import Problem


def wav(seconds=1.0, rate=16000):
    data=io.BytesIO()
    with wave.open(data,"wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0"*int(seconds*rate))
    return data.getvalue()

class SpeechChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='asr-test-')
        root=Path(self.tmp.name)
        (root/'credentials').mkdir(mode=0o700)
        self.path=root/'credentials'/'siliconflow-asr.key'
        self.path.write_text('sk-test-public-fixture-123',encoding='utf8')
        self.path.chmod(0o600)
        self.server=NS(services=NS(paths=NS(root=root)))
        self.user=NS(id=174)
        asr.RECENT.clear()

    def tearDown(self):
        self.tmp.cleanup()
        asr.RECENT.clear()

    def upload(self,data=None,content_type='audio/wav'):
        return UploadFile(file=io.BytesIO(wav() if data is None else data),
                          filename='dictation.wav',headers=Headers({'content-type':content_type}))

    def test_pcm_valid_and_duration(self):
        self.assertEqual(asr.validate_wave(wav(2.5)),2.5)

    def test_rejects_empty_non_wave_truncated_and_long_audio(self):
        for raw in (b'',b'not audio',wav()[:-4],wav(121)):
            with self.subTest(length=len(raw)),self.assertRaises(Problem):
                asr.validate_wave(raw)

    def test_rejects_wrong_channels_width_or_duration(self):
        with self.assertRaises(Problem):asr.validate_wave(wav(.1))
        data=io.BytesIO()
        with wave.open(data,'wb') as f:
            f.setnchannels(2);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0\0\0\0'*16000)
        with self.assertRaises(Problem):asr.validate_wave(data.getvalue())

    def test_private_key_required_and_permissions(self):
        self.assertEqual(asr.api_key(self.server),'sk-test-public-fixture-123')
        self.path.chmod(0o644)
        with self.assertRaises(Problem):asr.api_key(self.server)
        self.path.unlink()
        with self.assertRaises(Problem):asr.api_key(self.server)

    def test_rate_limit_and_user_separation(self):
        for _ in range(8):asr.rate_check(12)
        with self.assertRaises(Problem):asr.rate_check(12)
        asr.rate_check(13)

    def test_transcription_only_returns_text_without_writing_message(self):
        async def go():
            fake=AsyncMock(return_value='会议明天下午三点举行')
            with patch.object(asr,'send_asr',fake):
                response=await asr.transcribe(file=self.upload(),user=self.user,server=self.server)
                fake.assert_awaited_once()
                raw,key=fake.call_args.args
                self.assertEqual(len(raw),len(wav()))
                self.assertTrue(key.startswith('sk-test-'))
                self.assertEqual(response['text'],'会议明天下午三点举行')
                self.assertFalse(response['auto_send'])
                self.assertEqual(response['duration_seconds'],1.0)
        asyncio.run(go())

    def test_invalid_mimetype_never_reaches_provider(self):
        async def go():
            with patch.object(asr,'send_asr',AsyncMock()) as fake:
                with self.assertRaises(Problem):
                    await asr.transcribe(file=self.upload(content_type='audio/webm'),user=self.user,server=self.server)
                fake.assert_not_awaited()
        asyncio.run(go())

    def test_status_does_not_expose_key(self):
        data=asr.status(user=self.user,server=self.server)
        self.assertTrue(data['configured'])
        self.assertEqual(data['model'],'FunAudioLLM/SenseVoiceSmall')
        self.assertNotIn('key',data)

if __name__=='__main__':unittest.main()
