#!/usr/bin/env python3
"""
Traditional Billing Recovery Token Provisioning Utility.
Explicit command to provision a one-time cryptographic recovery authorization token
for company details and Administrator credential recovery.

Usage:
    python scripts/provision_traditional_recovery_token.py
    python scripts/provision_traditional_recovery_token.py --force
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
from services.traditional_recovery_token import (
    get_canonical_recovery_token_path,
    provision_recovery_token,
)


def main():
    parser = argparse.ArgumentParser(
        description="Provision a one-time recovery token for Traditional Billing company & administrator recovery."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rotate and overwrite an existing unconsumed recovery token.",
    )
    args = parser.parse_args()

    company_service = TraditionalCompanyService(traditional_db_manager)

    try:
        count = company_service.get_company_count()
    except Exception as e:
        print(f"\n[ERROR] Unable to inspect Traditional Billing database: {e}", file=sys.stderr)
        sys.exit(1)

    if count == 0:
        print(
            "\n[RECOVERY BLOCKED] No company exists in the Traditional Billing database.\n"
            "Initial setup is required before recovery can be performed.\n"
            "Please run: python scripts/provision_traditional_setup_token.py\n",
            file=sys.stderr,
        )
        sys.exit(1)

    token_path = get_canonical_recovery_token_path()
    success, token, msg = provision_recovery_token(count, token_path=token_path, force=args.force)

    if not success:
        if token:
            print(f"\n[INFO] {msg}")
            print(f"Token Path:     {token_path}")
            print(f"Existing Token: {token}")
            print("\nTo rotate this token, run:")
            print("    python scripts/provision_traditional_recovery_token.py --force\n")
            sys.exit(0)
        else:
            print(f"\n[ERROR] {msg}\n", file=sys.stderr)
            sys.exit(1)

    border = "=" * 78
    print(f"\n{border}")
    print("TRADITIONAL BILLING — RECOVERY AUTHORIZATION TOKEN PROVISIONED")
    print(border)
    print(f"\nRecovery Token:  {token}")
    print(f"Token Location:  {token_path}")
    print("\nNext Steps:")
    print("1. Launch the Anti-Matrix Billing application.")
    print("2. On the Traditional Billing Login screen, click:")
    print("   '🛡️ Company & Account Recovery'")
    print("3. Review / update company details and Administrator credentials.")
    print("4. When prompted by the native system security dialog, enter the token above.")
    print("5. The token will be securely verified in Python and consumed upon commit.\n")
    print("SECURITY NOTE:")
    print("- This token is valid for one-time recovery.")
    print("- It is stored with owner-only (0600) permissions.")
    print(f"{border}\n")


if __name__ == "__main__":
    main()
