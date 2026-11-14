"""
Traditional Billing Bootstrap Setup Token Lifecycle Manager.
Implements secure, one-time bootstrap token generation, storage with 0600 permissions,
constant-time verification, and post-commit consumption.
Completely isolated from Fast Billing.
"""

import os
import secrets
from pathlib import Path
from typing import Optional, Tuple

from core.configuration import config
from core.logging_config import logger


def get_canonical_setup_token_path() -> Path:
    """
    Returns the canonical absolute path to the Traditional Billing bootstrap setup token.
    Resolves strictly within config.DATA_DIR.
    """
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return (config.DATA_DIR / ".traditional_setup_token").resolve()


def provision_setup_token(
    company_count: int,
    token_path: Optional[Path] = None,
    force: bool = False,
) -> Tuple[bool, str, str]:
    """
    Explicitly provisions a cryptographically secure bootstrap token for initial setup.

    Rules:
    1. If company_count > 0, initial setup is permanently locked out. Refuses provisioning.
    2. Does not overwrite an existing valid token unless force=True.
    3. Uses atomic exclusive creation (O_CREAT | O_EXCL) with 0600 permissions
       to eliminate race conditions and enforce owner-only read/write.
    4. Generates token using secrets.token_hex(24) (48 hex characters).
    5. Returns (success: bool, token: str, message: str).
    """
    target_path = (token_path or get_canonical_setup_token_path()).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Authoritative permanent lockout check
    if company_count > 0:
        if target_path.exists():
            try:
                target_path.unlink(missing_ok=True)
            except Exception:
                pass
        return False, "", "Initial setup is permanently locked out. One or more companies already exist."

    # 2. Existing token check (do not silently overwrite)
    if target_path.exists() and not force:
        try:
            existing = target_path.read_text(encoding="utf-8").strip()
            if existing:
                return False, existing, f"A valid bootstrap token already exists at '{target_path}'. Existing token preserved."
        except Exception:
            pass

    # 3. Cryptographically strong token generation
    token = secrets.token_hex(24)

    # 4. Atomic file creation with restrictive 0600 permissions
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if force else os.O_EXCL)
    try:
        fd = os.open(str(target_path), flags, 0o600)
    except FileExistsError:
        # Concurrent provisioning attempt caught
        existing = target_path.read_text(encoding="utf-8").strip()
        return False, existing, f"Concurrent provisioning detected. Existing token preserved at '{target_path}'."

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(token + "\n")
        # Ensure chmod 0600 on POSIX even if umask modified it
        try:
            os.chmod(target_path, 0o600)
        except Exception:
            pass
    except Exception as e:
        return False, "", f"Failed to write bootstrap token file: {e}"

    return True, token, f"Bootstrap setup token successfully provisioned at '{target_path}'."


def verify_setup_token(entered_token: str, token_path: Optional[Path] = None) -> bool:
    """
    Verifies the entered token against the stored token using constant-time comparison.
    Fails closed if the token file is missing, empty, or unreadable.
    """
    if not entered_token or not entered_token.strip():
        return False

    target_path = (token_path or get_canonical_setup_token_path()).resolve()
    if not target_path.exists():
        return False

    try:
        expected = target_path.read_text(encoding="utf-8").strip()
        if not expected:
            return False
        return secrets.compare_digest(entered_token.strip(), expected)
    except Exception as e:
        logger.warning(f"Error reading bootstrap token file during verification: {e}")
        return False


def consume_setup_token(token_path: Optional[Path] = None) -> bool:
    """
    Overwrites the token file with zeros and unlinks it post-commit.
    """
    target_path = (token_path or get_canonical_setup_token_path()).resolve()
    if not target_path.exists():
        return True

    try:
        target_path.write_text("0" * 48, encoding="utf-8")
        target_path.unlink(missing_ok=True)
        return True
    except Exception as e:
        logger.warning(f"Error removing bootstrap setup token post-commit: {e}")
        return False
