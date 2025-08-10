import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "users.db"
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x]  # misol: "12345678,87654321"
