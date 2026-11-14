#!/usr/bin/env python3
"""
Traditional Billing Bootstrap Token Provisioning Utility.
Explicit command to provision a one-time cryptographic bootstrap token
for initial company and administrator setup.

Usage:
    python scripts/provision_traditional_setup_token.py
    python scripts/provision_traditional_setup_token.py --force
"""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.configuration import config
from db.traditional_database import traditional_db_manager
from services.traditional_company_service import TraditionalCompanyService
from services.traditional_setup_token import (
    get_canonical_setup_token_path,
    provision_setup_token,
)


def main():
    parser = argparse.ArgumentParser(
        description="Provision a one-time bootstrap token for Traditional Billing initial setup."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rotate and overwrite an existing unconsumed setup token.",
    )
    args = parser.parse_args()

    company_service = TraditionalCompanyService(traditional_db_manager)

    try:
        count = company_service.get_company_count()
    except Exception as e:
        print(f"\n[ERROR] Unable to inspect Traditional Billing database: {e}", file=sys.stderr)
        sys.exit(1)

    if count > 0:
        print(
            "\n[ERROR] Initial setup is permanently locked out.\n"
            f"Traditional Billing already has {count} registered company/companies.\n"
            "Bootstrap tokens cannot be generated for an existing installation.",
            file=sys.stderr,
        )
        sys.exit(1)

    token_path = get_canonical_setup_token_path()

    success, token, msg = provision_setup_token(count, token_path=token_path, force=args.force)

    if not success and not args.force:
        print("\n" + "=" * 74)
        print("TRADITIONAL BILLING — EXISTING BOOTSTRAP TOKEN DETECTED")
        print("=" * 74)
        print(f"Target Path: {token_path}")
        print("\n" + msg)
        print("\nINSTRUCTIONS:")
        print("A valid token already exists in the protected file above.")
        print("Use the existing token in the desktop application setup prompt.")
        print("If you need to replace it before setup, re-run with --force:")
        print("    python scripts/provision_traditional_setup_token.py --force")
        print("=" * 74 + "\n")
        sys.exit(0)

    if not success:
        print(f"\n[ERROR] Failed to provision bootstrap token: {msg}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 74)
    print("TRADITIONAL BILLING — ONE-TIME BOOTSTRAP SETUP TOKEN")
    print("=" * 74)
    print(f"Token Path:   {token_path}")
    print(f"Permissions:  0600 (Owner Read/Write Only)")
    print(f"Status:       Active (Single-use, destroyed upon setup commit)")
    print("-" * 74)
    print("BOOTSTRAP SETUP TOKEN:")
    print(f"    {token}")
    print("-" * 74)
    print("OPERATOR INSTRUCTIONS:")
    print("1. Keep this token strictly confidential. It authorizes the creation")
    print("   of the initial Master Company and System Administrator.")
    print("2. Launch the desktop application and select 'Traditional Billing'.")
    print("3. Click 'Launch Initial Company Setup' and enter your company details.")
    print("4. When the native desktop dialog prompts for authorization, enter")
    print("   the token displayed above.")
    print("5. Upon successful setup, this token file is automatically wiped and deleted.")
    print("=" * 74 + "\n")


if __name__ == "__main__":
    main()
