import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/rpg.sqlite3")
TIMEZONE = os.getenv("TIMEZONE", "UTC")

MAX_ENERGY = 10
ENERGY_REGEN_SECONDS = 300
