import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "neon_scratch.db"
))

LORE_DIR = os.getenv("LORE_DIR", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lore"
))

XP_PER_LEVEL = int(os.getenv("XP_PER_LEVEL", "100"))
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "20"))
HISTORY_TRIM_COUNT = int(os.getenv("HISTORY_TRIM_COUNT", "5"))
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "12"))

FORCE_TOOL_FAILURE = False

DM_MODE = os.getenv("DM_MODE", "single_shot")
# "agentic" — LLM decides which tools to call (multi-turn, requires capable model)
# "single_shot" — engine calculates mechanics, LLM only narrates (faster, works on small models)

LOCALE = os.getenv("LOCALE", "pt-BR")
# "en-US" — English
# "pt-BR" — Brazilian Portuguese
