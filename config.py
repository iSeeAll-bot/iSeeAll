import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
HTTP_PROXY = os.getenv("HTTP_PROXY", "").strip()
HTTPS_PROXY = os.getenv("HTTPS_PROXY", "").strip()

OWNER_ID_STR = os.getenv("OWNER_ID", "0").strip()
OWNER_ID = int(OWNER_ID_STR) if OWNER_ID_STR.isdigit() else 0

CACHE_DAYS = int(os.getenv("CACHE_DAYS", "30"))

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "business_messages.db"
MEDIA_DIR = BASE_DIR / "saved_media"

DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
