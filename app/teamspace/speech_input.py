"""Authenticated, bounded speech-to-text. Recordings are not added to project knowledge."""
from __future__ import annotations
import asyncio
import io
import os
import stat
import time
import wave
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, UploadFile
from octop.api.deps import current_user, get_server

from .store import Problem

router = APIRouter()
MODEL = "FunAudioLLM/SenseVoiceSmall"
ENDPOINT = "https://api.siliconflow.cn/v1/audio/transcriptions"
MAX_BYTES = 8 * 1024 * 1024
MAX_SECONDS = 120
SLOTS = asyncio.Semaphore(2)
RECENT: dict[int, deque[float]] = defaultdict(deque)

def key_path(server: Any) -> Path:
    root = Path(server.services.paths.root)
    return root / "credentials" / "siliconflow-asr.key"

def api_key(server: Any) -> str:
    path = key_path(server)
    if not path.is_file() or path.is_symlink():
        raise Problem(503, "语音识别尚未由部署管理员配置")
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise Problem(503, "语音识别凭证权限不安全，请联系部署管理员")
    key = path.read_text(encoding="utf-8").strip()
    if not key.startswith("sk-") or not 20 <= len(key) <= 256:
        raise Problem(503, "语音识别凭证格式无效")
    return key

def validate_wave(raw: bytes) -> float:
    if len(raw) > MAX_BYTES:
        raise Problem(413, "语音文件不能超过8MB")
    if len(raw) < 48 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise Problem(422, "请使用麦克风录制的 WAV 音频")
    try:
        with wave.open(io.BytesIO(raw), "rb") as audio:
            channels = audio.getnchannels()
            width = audio.getsampwidth()
            rate = audio.getframerate()
            frames = audio.getnframes()
            if audio.getcomptype() != "NONE" or channels != 1 or width != 2 or not 8000 <= rate <= 48000:
                raise ValueError("Unsupported PCM format")
            duration = frames / rate
            if not 0.25 <= duration <= MAX_SECONDS:
                raise Problem(422, "录音长度应在0.25秒至120秒之间")
            samples = audio.readframes(frames)
            if len(samples) != frames * channels * width:
                raise ValueError("Audio bytes were truncated")
            return duration
    except (EOFError, ValueError, wave.Error):
        raise Problem(422, "音频文件无效或不完整") from None

async def send_asr(audio: bytes, key: str) -> str:
    timeout = httpx.Timeout(connect=10, read=80, write=25, pool=10)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            response = await client.post(
                ENDPOINT,
                headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
                data={"model": MODEL},
                files={"file": ("recording.wav", audio, "audio/wav")},
            )
    except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError):
        raise Problem(504, "语音识别服务暂时不可用，请重新尝试；输入框内容未改变") from None
    if response.status_code in (401, 403):
        raise Problem(502, "语音识别服务授权失败，请联系管理员")
    if response.status_code == 429:
        raise Problem(429, "语音识别服务限流，请稍后再试")
    if response.status_code != 200:
        raise Problem(502, "语音识别服务暂时无法处理该录音")
    try:
        data = response.json()
    except ValueError:
        raise Problem(502, "语音识别服务返回格式无效") from None
    text = data.get("text") if isinstance(data, dict) else None
    if not isinstance(text, str) or len(text) > 30000:
        raise Problem(502, "语音识别未返回有效文本")
    return text.strip()

def rate_check(actor: int) -> None:
    now = time.monotonic()
    entries = RECENT[actor]
    while entries and now - entries[0] >= 60:
        entries.popleft()
    if len(entries) >= 8:
        raise Problem(429, "语音识别调用较频繁，请稍后再试")
    entries.append(now)
    if len(RECENT) > 500:
        for uid in list(RECENT):
            if not RECENT[uid] or now - RECENT[uid][-1] > 60:
                RECENT.pop(uid, None)

@router.get("/asr/status")
def status(user: Any = Depends(current_user), server: Any = Depends(get_server)):
    path = key_path(server)
    available = path.is_file() and not path.is_symlink() and not path.stat().st_mode & 0o077
    return {"configured": bool(available), "model": MODEL, "max_seconds": MAX_SECONDS, "max_bytes": MAX_BYTES}

@router.post("/asr/transcriptions")
async def transcribe(file: UploadFile = File(...), user: Any = Depends(current_user), server: Any = Depends(get_server)):
    if file.content_type not in ("audio/wav", "audio/wave", "audio/x-wav"):
        raise Problem(422, "只支持麦克风录制的 WAV 音频")
    raw = await file.read(MAX_BYTES + 1)
    duration = validate_wave(raw)
    key = api_key(server)
    rate_check(user.id)
    try:
        await asyncio.wait_for(SLOTS.acquire(), timeout=3)
    except asyncio.TimeoutError:
        raise Problem(429, "语音识别正在忙碌，请稍后再试") from None
    try:
        text = await send_asr(raw, key)
    finally:
        SLOTS.release()
        await file.close()
    return {"text": text, "duration_seconds": round(duration, 2), "model": MODEL, "auto_send": False}
