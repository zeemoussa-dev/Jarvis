from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

import config
from core.audio import play_audio_bytes

_client: ElevenLabs | None = None


def _get_client() -> ElevenLabs:
    global _client
    if _client is None:
        _client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
    return _client


def speak(text: str) -> None:
    """Convert text to speech using ElevenLabs and play it immediately."""
    print(f"[JARVIS] {text}")
    client = _get_client()
    audio = client.text_to_speech.convert(
        voice_id=config.ELEVENLABS_VOICE_ID,
        text=text,
        model_id=config.TTS_MODEL,
        voice_settings=VoiceSettings(
            stability=config.TTS_STABILITY,
            similarity_boost=config.TTS_SIMILARITY_BOOST,
            style=config.TTS_STYLE,
            use_speaker_boost=config.TTS_SPEAKER_BOOST,
        ),
        output_format="mp3_44100_128",
    )
    audio_bytes = b"".join(audio)
    play_audio_bytes(audio_bytes)
