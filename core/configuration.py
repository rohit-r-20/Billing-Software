"""
Application Configuration for Anti Matrix Billing ERP.
Centralizes paths, database settings, and operational flags.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Automatically load environment variables from .env if present
_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env")


class AppConfig:
    APP_NAME = "Alpha Billing"
    APP_DISPLAY_NAME = "Alpha Billing Cloud ERP"
    VENDOR_NAME = "Alpha Billing"
    VERSION = "2.5.0"
    
    # Base directory of the application
    BASE_DIR = _BASE_DIR
    
    # User data directory: defaults to local data/ for development/portable, or AppData
    DATA_DIR = BASE_DIR / "data"
    BACKUP_DIR = BASE_DIR / "backups"
    
    # Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Canonical database path
    DATABASE_PATH = DATA_DIR / "anti_matrix_billing.db"
    
    # Currency and precision
    CURRENCY_SYMBOL = "₹"
    CURRENCY_CODE = "INR"
    MONEY_DECIMALS = 2
    QUANTITY_DECIMALS = 3  # Support 0.250 kg, 1.500 kg
    
    # Default GST Rates in India
    SUPPORTED_GST_RATES = [0.0, 5.0, 12.0, 18.0, 28.0]
    DEFAULT_GST_RATE = 18.0
    
    # Thermal Receipt Settings
    THERMAL_WIDTH_58MM = 32  # characters
    THERMAL_WIDTH_80MM = 48  # characters
    DEFAULT_RECEIPT_WIDTH = 80
    
    @classmethod
    def get_database_url(cls) -> str:
        """
        Retrieves the canonical database connection string.
        Prioritizes DATABASE_URL (12-factor / Supabase / standard PostgreSQL),
        then ANTI_MATRIX_DATABASE_URL, falling back to local SQLite.
        """
        # 1. Standard DATABASE_URL
        url = os.getenv("DATABASE_URL")
        if url and url.strip():
            return url.strip()

        # 2. Legacy ANTI_MATRIX_DATABASE_URL
        legacy_url = os.getenv("ANTI_MATRIX_DATABASE_URL")
        if legacy_url and legacy_url.strip():
            return legacy_url.strip()

        # 3. Default SQLite fallback
        return f"sqlite:///{cls.DATABASE_PATH}"

    @classmethod
    def is_postgres(cls) -> bool:
        """Returns True if the active database URL targets PostgreSQL."""
        url = cls.get_database_url().lower()
        return url.startswith("postgres://") or url.startswith("postgresql://") or url.startswith("postgresql+")

    @classmethod
    def is_sqlite(cls) -> bool:
        """Returns True if the active database URL targets SQLite."""
        url = cls.get_database_url().lower()
        return url.startswith("sqlite://") or url.startswith("sqlite:")

    @classmethod
    def get_database_dialect(cls) -> str:
        """Returns the active database dialect name ('postgresql' or 'sqlite')."""
        if cls.is_postgres():
            return "postgresql"
        return "sqlite"


config = AppConfig

