import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://loguser:localdevpassword@localhost:5432/logmonitor",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
