import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Use ephemeral SQLite in /tmp/test.db as zero-config fallback on Vercel if no DATABASE_URL is set
    default_db = "sqlite:////tmp/test.db" if os.getenv("VERCEL") == "1" else "postgresql://postgres:postgres@localhost:5432/hostel_db"
    DATABASE_URL: str = os.getenv("DATABASE_URL", default_db)
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-jwt-key-change-in-production-123456")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # Standard billing / rebate defaults
    DEFAULT_MONTHLY_BASE_FEE: float = 5000.00
    DAILY_MESS_REBATE_RATE: float = 150.00

settings = Settings()
