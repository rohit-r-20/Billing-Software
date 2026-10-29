"""
Application Configuration for Anti Matrix Billing ERP.
Centralizes paths, database settings, and operational flags.
"""
import os
import sys
from pathlib import Path


class AppConfig:
    APP_NAME = "Alpha Billing Software"
    APP_DISPLAY_NAME = "Anti Matrix Billing ERP"
    VENDOR_NAME = "Anti Matrix"
    VERSION = "2.1.0"
    
    # Base directory of the application
    BASE_DIR = Path(__file__).resolve().parent.parent
    
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
        # SQLite URL or custom PostgreSQL URL if configured via env
        env_url = os.getenv("ANTI_MATRIX_DATABASE_URL")
        if env_url:
            return env_url
        return f"sqlite:///{cls.DATABASE_PATH}"


config = AppConfig

