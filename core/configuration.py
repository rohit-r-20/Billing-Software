"""
Application Configuration for Alpha Billing ERP.
Centralizes paths, database settings, environment variables, and operational flags.
"""
import os
import re
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Base directory of the application: support development, testing, and PyInstaller frozen bundle
if getattr(sys, "frozen", False):
    _BASE_DIR = Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()
    if not (_BASE_DIR / "index.html").exists():
        _BASE_DIR = Path(sys.executable).parent.resolve()
else:
    _BASE_DIR = Path(__file__).resolve().parent.parent

# User data & backup directories: supports env override, user AppData in frozen mode, or local project dir
_DATA_DIR_ENV = os.getenv("APP_DATA_DIR") or os.getenv("ANTI_MATRIX_DATA_DIR")
if _DATA_DIR_ENV and _DATA_DIR_ENV.strip():
    _DEFAULT_DATA_DIR = Path(_DATA_DIR_ENV.strip()).resolve()
elif getattr(sys, "frozen", False):
    if sys.platform == "darwin":
        _DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "AntiMatrixBilling" / "data"
    elif sys.platform == "win32":
        _DEFAULT_DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "AntiMatrixBilling" / "data"
    else:
        _DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "anti-matrix-billing" / "data"
else:
    _DEFAULT_DATA_DIR = _BASE_DIR / "data"

_BACKUP_DIR_ENV = os.getenv("APP_BACKUP_DIR") or os.getenv("ANTI_MATRIX_BACKUP_DIR")
if _BACKUP_DIR_ENV and _BACKUP_DIR_ENV.strip():
    _DEFAULT_BACKUP_DIR = Path(_BACKUP_DIR_ENV.strip()).resolve()
elif getattr(sys, "frozen", False):
    if sys.platform == "darwin":
        _DEFAULT_BACKUP_DIR = Path.home() / "Library" / "Application Support" / "AntiMatrixBilling" / "backups"
    elif sys.platform == "win32":
        _DEFAULT_BACKUP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "AntiMatrixBilling" / "backups"
    else:
        _DEFAULT_BACKUP_DIR = Path.home() / ".local" / "share" / "anti-matrix-billing" / "backups"
else:
    _DEFAULT_BACKUP_DIR = _BASE_DIR / "backups"

# Profile detection and 12-factor dotenv loading
_RAW_ENV = (os.getenv("APP_ENV") or os.getenv("DATABASE_ENV") or "").strip().lower()

if _RAW_ENV == "staging":
    # In staging, strictly isolate from production .env
    if (_BASE_DIR / ".env.staging").exists():
        load_dotenv(_BASE_DIR / ".env.staging", override=True)
elif _RAW_ENV == "testing":
    # In testing, strictly isolate from production .env
    if (_BASE_DIR / ".env.testing").exists():
        load_dotenv(_BASE_DIR / ".env.testing", override=True)
else:
    # Development or production default
    load_dotenv(_BASE_DIR / ".env")
    # If .env itself specifies APP_ENV=staging, switch and load .env.staging
    _DETECTED_ENV = (os.getenv("APP_ENV") or os.getenv("DATABASE_ENV") or "").strip().lower()
    if _DETECTED_ENV == "staging" and (_BASE_DIR / ".env.staging").exists():
        load_dotenv(_BASE_DIR / ".env.staging", override=True)


class AppConfig:
    APP_NAME = "Alpha Billing"
    APP_DISPLAY_NAME = "Alpha Billing Cloud ERP"
    VENDOR_NAME = "Alpha Billing"
    VERSION = "2.5.0"
    
    # Base directory of the application
    BASE_DIR = _BASE_DIR
    
    # User data directory: defaults to local data/ for development/portable, or AppData
    DATA_DIR = _DEFAULT_DATA_DIR
    BACKUP_DIR = _DEFAULT_BACKUP_DIR
    
    # Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Canonical database path for historical SQLite (default development path)
    DATABASE_PATH = DATA_DIR / "anti_matrix_billing.db"
    TRADITIONAL_DATABASE_PATH = DATA_DIR / "traditional_billing.db"
    
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

    # =========================================================================
    # Profile & Environment Configuration
    # =========================================================================

    @classmethod
    def get_environment(cls) -> str:
        """
        Retrieves the normalized active environment profile:
        'development', 'staging', 'production', or 'testing'.
        Defaults to 'development'.
        """
        env = (os.getenv("APP_ENV") or os.getenv("DATABASE_ENV") or "development").strip().lower()
        if env not in ("development", "staging", "production", "testing"):
            return "development"
        return env

    @classmethod
    def is_development(cls) -> bool:
        return cls.get_environment() == "development"

    @classmethod
    def is_staging(cls) -> bool:
        return cls.get_environment() == "staging"

    @classmethod
    def is_production(cls) -> bool:
        return cls.get_environment() == "production"

    @classmethod
    def is_testing(cls) -> bool:
        return cls.get_environment() == "testing"

    @classmethod
    def get_database_path(cls) -> Path:
        """
        Retrieves the canonical SQLite database path for Fast Billing based on active profile.
        """
        custom_path = os.getenv("FAST_DATABASE_PATH")
        if custom_path and custom_path.strip():
            return Path(custom_path.strip()).resolve()

        env = cls.get_environment()
        if env == "staging":
            return cls.DATA_DIR / "staging_anti_matrix_billing.db"
        elif env == "testing":
            return cls.DATA_DIR / "test_anti_matrix_billing.db"
        return cls.DATA_DIR / "anti_matrix_billing.db"

    @classmethod
    def get_traditional_database_path(cls) -> Path:
        """
        Retrieves the canonical SQLite database path for Traditional Billing based on active profile.
        """
        custom_path = os.getenv("TRADITIONAL_DATABASE_PATH")
        if custom_path and custom_path.strip():
            return Path(custom_path.strip()).resolve()

        env = cls.get_environment()
        if env == "staging":
            return cls.DATA_DIR / "staging_traditional_billing.db"
        elif env == "testing":
            return cls.DATA_DIR / "test_traditional_billing.db"
        return cls.DATA_DIR / "traditional_billing.db"

    # =========================================================================
    # Database Abstraction & Environment Configuration
    # =========================================================================

    @classmethod
    def get_database_env(cls) -> str:
        """
        Retrieves the active database environment (development, staging, production, testing).
        Defaults to 'development'.
        """
        return cls.get_environment()

    @classmethod
    def get_database_url(cls) -> str:
        """
        Retrieves the canonical database connection string for Fast Billing.
        Prioritizes STAGING_DATABASE_URL in staging mode,
        then DATABASE_URL (12-factor / Supabase / standard PostgreSQL),
        then SUPABASE_DATABASE_URL, then legacy ANTI_MATRIX_DATABASE_URL,
        falling back to profile-specific local SQLite if no PostgreSQL URL is configured.
        """
        if cls.is_staging():
            staging_url = os.getenv("STAGING_DATABASE_URL")
            if staging_url and staging_url.strip():
                return staging_url.strip()
            url = os.getenv("DATABASE_URL")
            if url and url.strip():
                return url.strip()
            return f"sqlite:///{cls.get_database_path()}"

        # 1. Standard DATABASE_URL
        url = os.getenv("DATABASE_URL")
        if url and url.strip():
            return url.strip()

        # 2. Supabase specific variable
        supabase_url = os.getenv("SUPABASE_DATABASE_URL")
        if supabase_url and supabase_url.strip():
            return supabase_url.strip()

        # 3. Legacy ANTI_MATRIX_DATABASE_URL
        legacy_url = os.getenv("ANTI_MATRIX_DATABASE_URL")
        if legacy_url and legacy_url.strip():
            return legacy_url.strip()

        # 4. Profile-aware SQLite fallback
        return f"sqlite:///{cls.get_database_path()}"

    @classmethod
    def get_pool_config(cls) -> dict:
        """
        Returns connection pool configuration parameters driven by environment.
        Desktop billing clients use conservative connection pool sizes to prevent
        exhausting database connection limits on managed cloud PostgreSQL (e.g. Supabase).
        """
        return {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300")),
            "pool_pre_ping": True,
        }

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

    @staticmethod
    def mask_database_url(url: Optional[str]) -> str:
        """
        Masks passwords and authentication tokens in a database connection URL
        for safe logging, diagnostic output, and user reports.
        """
        if not url:
            return ""
        # Mask standard URI credentials: user:pass@host -> user:****@host
        masked = re.sub(r"://([^:@/]+):([^@/]+)@", r"://\1:****@", url)
        return masked

    @classmethod
    def validate_configuration(cls) -> dict:
        """
        Validates active environment profile, database configurations, and filesystem permissions.
        Returns a diagnostic dictionary:
        {
            "valid": bool,
            "environment": str,
            "fast_db_url_masked": str,
            "traditional_db_url_masked": str,
            "data_dir_writable": bool,
            "backup_dir_writable": bool,
            "errors": list[str],
            "warnings": list[str]
        }
        """
        env = cls.get_environment()
        errors = []
        warnings = []

        # 1. Directory writability checks
        data_writable = os.access(cls.DATA_DIR, os.W_OK)
        if not data_writable:
            errors.append(f"Data directory is not writable: {cls.DATA_DIR}")

        backup_writable = os.access(cls.BACKUP_DIR, os.W_OK)
        if not backup_writable:
            warnings.append(f"Backup directory is not writable: {cls.BACKUP_DIR}")

        # 2. Database URLs
        fast_url = cls.get_database_url()
        trad_url = os.getenv("TRADITIONAL_DATABASE_URL") or f"sqlite:///{cls.get_traditional_database_path()}"

        # 3. Physical isolation check
        norm_fast = fast_url.strip().lower()
        norm_trad = trad_url.strip().lower()
        if norm_fast == norm_trad:
            errors.append("Fast Billing and Traditional Billing databases cannot share the same database target.")

        # 4. Profile-specific safety guards
        if env == "staging":
            # Guard against connecting staging to production SQLite databases
            prod_fast_name = "anti_matrix_billing.db"
            prod_trad_name = "traditional_billing.db"
            if norm_fast.endswith(f"/{prod_fast_name}") or norm_fast.endswith(f"\\{prod_fast_name}"):
                errors.append(
                    "Staging profile is configured with production Fast Billing database (anti_matrix_billing.db). "
                    "Use staging database (staging_anti_matrix_billing.db)."
                )
            if norm_trad.endswith(f"/{prod_trad_name}") or norm_trad.endswith(f"\\{prod_trad_name}"):
                errors.append(
                    "Staging profile is configured with production Traditional Billing database (traditional_billing.db). "
                    "Use staging database (staging_traditional_billing.db)."
                )
            # Guard against connecting staging to production remote database
            if ("postgres" in norm_fast or "supabase" in norm_fast) and not ("staging" in norm_fast or "test" in norm_fast):
                errors.append(
                    "Staging profile is configured with a non-staging PostgreSQL/Supabase database URL. "
                    "Staging requires local SQLite or an explicitly designated staging database."
                )

        return {
            "valid": len(errors) == 0,
            "environment": env,
            "fast_db_url_masked": cls.mask_database_url(fast_url),
            "traditional_db_url_masked": cls.mask_database_url(trad_url),
            "data_dir_writable": data_writable,
            "backup_dir_writable": backup_writable,
            "errors": errors,
            "warnings": warnings,
        }


config = AppConfig
