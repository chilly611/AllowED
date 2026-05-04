"""Application configuration loaded from .env"""
from dotenv import dotenv_values
import os

_config = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))

SUPABASE_URL = _config.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = _config.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = _config.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Derived
PROJECT_REF = SUPABASE_URL.split("//")[1].split(".")[0] if "//" in SUPABASE_URL else ""
