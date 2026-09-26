"""Defaults for the xAI Grok HTTPS API."""

INFERENCE_BASE_URL = "https://api.x.ai"
MANAGEMENT_BASE_URL = "https://management-api.x.ai"
INFERENCE_HOSTS = frozenset({"api.x.ai"})
MANAGEMENT_HOSTS = frozenset({"management-api.x.ai"})

DEFAULT_TEXT_MODEL = "grok-4.6"
DEFAULT_IMAGE_MODEL = "grok-imagine-image-2.0"
DEFAULT_EMBEDDING_MODEL = "grok-embedding-small"
DEFAULT_VOICE_ID = "eve"
DEFAULT_REALTIME_MODEL = "grok-voice-latest"

DEFAULT_HTTP_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_RETRIES = 2
MAX_HTTP_TIMEOUT_SECONDS = 900.0
MAX_JSON_REQUEST_BYTES = 32 * 1024 * 1024
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
MAX_FILE_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_STT_UPLOAD_BYTES = 500 * 1024 * 1024
MAX_TTS_CHARACTERS = 15_000
MAX_PAGINATION_PAGES = 100
USER_AGENT = "salt-grok-client/1.0"

IMAGE_ASPECT_RATIOS = frozenset(
    {
        "1:1",
        "3:4",
        "4:3",
        "9:16",
        "16:9",
        "2:3",
        "3:2",
        "9:19.5",
        "19.5:9",
        "9:20",
        "20:9",
        "1:2",
        "2:1",
        "21:9",
        "5:2",
        "auto",
    }
)
IMAGE_RESOLUTIONS = frozenset({"1k", "2k", "1.5k"})
VIDEO_ASPECT_RATIOS = frozenset({"1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"})
VIDEO_RESOLUTIONS = frozenset({"480p", "720p", "1080p"})
SERVICE_TIERS = frozenset({"default", "priority", "fast"})
TTS_CODECS = frozenset({"mp3", "wav", "pcm", "mulaw", "alaw"})
AUDIO_SAMPLE_RATES = frozenset({8000, 16000, 22050, 24000, 44100, 48000})
MP3_BIT_RATES = frozenset({32000, 64000, 96000, 128000, 192000})
REALTIME_MODELS = frozenset(
    {"grok-voice-latest", "grok-voice-think-fast-2.0", "grok-voice-think-fast-1.0"}
)
