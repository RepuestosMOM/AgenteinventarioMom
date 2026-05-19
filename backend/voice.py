# ─────────────────────────────────────────────────────────────────
# VOICE — Google Cloud Speech-to-Text y Text-to-Speech
# ─────────────────────────────────────────────────────────────────
import logging
import re

from google.cloud import speech, texttospeech

log = logging.getLogger(__name__)

# ── Mapa MIME → encoding Cloud STT ───────────────────────────────
_MIME_TO_ENCODING = {
    "audio/webm":       speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
    "audio/webm;codecs=opus": speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
    "audio/ogg":        speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
    "audio/ogg;codecs=opus": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
    "audio/mp4":        speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED,
    "audio/mpeg":       speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED,
}


def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """Transcribe audio bytes a texto usando Cloud Speech-to-Text."""
    client = speech.SpeechClient()

    # Normalizar mime type (quitar parámetros extra antes de lookup)
    mime_key = mime_type.split(";")[0].strip().lower()
    # Si tiene codecs=opus en el mime_type original, incluirlo en la clave
    if "codecs=opus" in mime_type.lower():
        mime_key = mime_key + ";codecs=opus"

    encoding = _MIME_TO_ENCODING.get(
        mime_type.lower(),
        _MIME_TO_ENCODING.get(mime_key, speech.RecognitionConfig.AudioEncoding.WEBM_OPUS)
    )

    config = speech.RecognitionConfig(
        encoding=encoding,
        language_code="es-CL",
        enable_automatic_punctuation=True,
        model="latest_short",  # optimizado para comandos cortos
        speech_contexts=[
            speech.SpeechContext(
                phrases=[
                    "amortiguador", "termostato", "pastillas", "discos",
                    "filtro", "correa", "bomba", "radiador", "alternador",
                    "Toyota", "Chevrolet", "Hilux", "Aveo", "Corolla",
                    "OEM", "stock", "bodega", "proveedor",
                ],
                boost=15.0,
            )
        ],
    )

    audio = speech.RecognitionAudio(content=audio_bytes)

    try:
        response = client.recognize(config=config, audio=audio)
    except Exception as exc:
        log.error("Cloud STT error: %s", exc)
        raise

    if not response.results:
        return ""

    return " ".join(
        result.alternatives[0].transcript
        for result in response.results
        if result.alternatives
    ).strip()


def synthesize_speech(text: str) -> bytes:
    """Convierte texto a audio MP3 usando Cloud Text-to-Speech."""
    client = texttospeech.TextToSpeechClient()

    # Limpiar marcadores markdown antes de sintetizar
    clean = re.sub(r"[*_`#>]", "", text)
    clean = re.sub(r"\n+", ". ", clean)
    clean = re.sub(r"\s{2,}", " ", clean).strip()
    clean = clean[:4500]  # límite seguro por debajo de los 5000 chars de la API

    synthesis_input = texttospeech.SynthesisInput(text=clean)

    voice = texttospeech.VoiceSelectionParams(
        language_code="es-US",
        name="es-US-Neural2-B",  # voz masculina neutral latinoamericana
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.05,
        pitch=0.0,
    )

    try:
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
    except Exception as exc:
        log.error("Cloud TTS error: %s", exc)
        raise

    return response.audio_content
