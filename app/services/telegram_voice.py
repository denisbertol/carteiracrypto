"""Serviço de download e transcrição de áudio do Telegram.

Atende a D-03, RF-01, e aos ensinamentos da Aula 4 (Prof. Sandeco):
- Sandboxing: grava áudios efêmeros exclusivamente em ./temp/ sanitizado.
- Higiene Efêmera: exclusão obrigatória (unlink) no bloco finally para não vazar mídia em disco.
- Transcrição multimodal em português via Whisper local ou Gemini.
- Falha de áudio ou transcrição é tratada com segurança sem gravar operações.
"""

import logging
import os
from pathlib import Path
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

TEMP_DIR = Path("./temp")


def ensure_temp_dir() -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_DIR


def download_telegram_voice_file(bot_token: str, file_id: str) -> Optional[Path]:
    """Baixa o arquivo de voz do Telegram para a pasta segura ./temp."""
    ensure_temp_dir()
    client = httpx.Client(timeout=15.0)
    try:
        # 1. Obtém o file_path do Telegram
        res = client.get(f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}")
        if res.status_code != 200:
            logger.error(f"Erro ao obter file_path do Telegram: {res.text}")
            return None
        data = res.json()
        if not data.get("ok"):
            return None

        file_path = data.get("result", {}).get("file_path")
        if not file_path:
            return None

        # 2. Faz download dos bytes
        file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        file_res = client.get(file_url)
        if file_res.status_code != 200:
            logger.error(f"Erro ao baixar áudio do Telegram: {file_res.status_code}")
            return None

        # Grava de forma segura no temp
        target_path = TEMP_DIR / f"voice_{file_id[-12:]}.ogg"
        target_path.write_bytes(file_res.content)
        return target_path
    except Exception as e:
        logger.error(f"Falha de rede ao baixar voz do Telegram: {e}")
        return None
    finally:
        client.close()


def transcribe_audio_file(audio_path: Path) -> Optional[str]:
    """Transcreve arquivo de áudio utilizando Whisper local se disponível."""
    if not audio_path.exists():
        return None

    try:
        import whisper
        model = whisper.load_model("tiny")
        result = model.transcribe(str(audio_path), language="pt")
        text = (result.get("text") or "").strip()
        return text if text else None
    except Exception as e:
        logger.warning(f"Whisper local não disponível ou falhou: {e}")
        return None


def process_telegram_voice(bot_token: str, file_id: str) -> Optional[str]:
    """Orquestra download, transcrição e higienização efêmera imediata do arquivo."""
    audio_path = download_telegram_voice_file(bot_token, file_id)
    if not audio_path:
        return None

    try:
        return transcribe_audio_file(audio_path)
    finally:
        # Higiene Efêmera mandatória (Aula 4 do Prof. Sandeco)
        try:
            if audio_path.exists():
                audio_path.unlink()
        except Exception as e:
            logger.warning(f"Erro ao limpar arquivo temporário de áudio: {e}")

