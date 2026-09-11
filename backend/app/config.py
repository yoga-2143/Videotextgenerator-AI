import os
from dotenv import load_dotenv

load_dotenv()

secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    raise ValueError("SECRET_KEY environment variable MUST be set. Please check your .env file or environment configuration.")


class Config:
    SECRET_KEY = secret_key
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///vetri.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

