# ─────────────────────────────────────────────────────────────────
# VOICE — Google Cloud Speech-to-Text y Text-to-Speech
# ─────────────────────────────────────────────────────────────────
import logging
import re

from google.cloud import speech, texttospeech

log = logging.getLogger(__name__)

# ── Mapa MIME → encoding Cloud STT ───────────────────────────────
def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Transcribe audio bytes a texto usando Cloud Speech-to-Text."""
    client = speech.SpeechClient()

    # El frontend siempre envía WAV/LINEAR16 a 16 kHz
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        audio_channel_count=1,
        language_code="es-CL",
        enable_automatic_punctuation=True,
        model="default",
        speech_contexts=[
            speech.SpeechContext(
                phrases=[
                    "amortiguador", "termostato", "pastillas", "discos de freno",
                    "filtro de aceite", "correa de distribución", "bomba de agua",
                    "radiador", "alternador", "bujías", "sensor", "inyector",
                    "Toyota", "Chevrolet", "Hilux", "Aveo", "Corolla", "Yaris",
                    "Ranger", "Spark", "N-300", "Duster", "Logan",
                    "OEM", "código OEM", "stock", "bodega", "referencia",
                ],
                boost=18.0,
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
        log.warning("STT devolvió 0 resultados para audio de %d bytes", len(audio_bytes))
        return ""

    transcript = " ".join(
        result.alternatives[0].transcript
        for result in response.results
        if result.alternatives
    ).strip()
    log.info("STT transcripción: %r", transcript)
    return transcript


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
