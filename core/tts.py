import re

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


def _clean(text: str) -> str:
    """Strip markdown so TTS doesn't read symbols aloud."""
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)   # bold / italic
    text = re.sub(r"_{1,2}(.+?)_{1,2}", r"\1", text)      # underscore emphasis
    text = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", text)      # inline code
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)  # headings
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)        # links
    text = re.sub(r"[#>~|]", "", text)                     # leftover symbols
    return text.strip()


def speak(text: str) -> None:
    """Convert text to speech using ElevenLabs and play it immediately."""
    text = _clean(text)
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
