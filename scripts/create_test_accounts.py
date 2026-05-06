#!/usr/bin/env python3
"""
Create test SCO accounts in Supabase Auth + sco_users table.

Creates:
  1. SDSU SCO      — sco@sdsu.test / AllowED2026!
  2. Cal Poly SCO  — sco@calpoly.test / AllowED2026!
  3. Superadmin    — admin@allowed.test / AllowED2026!

Usage:
  python3 scripts/create_test_accounts.py
"""

import os
import sys

try:
    from dotenv import dotenv_values
except ImportError:
    print("ERROR: python-dotenv not installed")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase not installed")
    sys.exit(1)

config = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
SUPABASE_URL = config.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = config.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

# Test accounts to create
TEST_ACCOUNTS = [
    {
        "email": "sco@sdsu.test",
        "password": "AllowED2026!",
        "full_name": "Paulina Enriquez",
        "institution_id": "11910105",  # SDSU
        "role": "sco",
    },
    {
        "email": "sco@calpoly.test",
        "password": "AllowED2026!",
        "full_name": "Test SCO (Cal Poly)",
        "institution_id": "11906105",  # Cal Poly Humboldt
        "role": "sco",
    },
    {
        "email": "admin@allowed.test",
        "password": "AllowED2026!",
        "full_name": "AllowED Admin",
        "institution_id": "11910105",  # Home institution SDSU
        "role": "superadmin",
    },
]


def main():
    print("=" * 60)
    print("AllowED — Create Test SCO Accounts")
    print("=" * 60)

    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    for account in TEST_ACCOUNTS:
        email = account["email"]
        print(f"\n--- {email} ({account['role']}) ---")

        # Check if user already exists in sco_users
        existing = client.table("sco_users").select("id").eq("email", email).execute()
        if existing.data:
            print(f"  Already exists (id: {existing.data[0]['id']}), skipping.")
            continue

        # Create auth user via admin API
        try:
            auth_response = client.auth.admin.create_user({
                "email": email,
                "password": account["password"],
                "email_confirm": True,  # Auto-confirm so they can log in immediately
                "app_metadata": {
                    "institution_id": account["institution_id"],
                    "role": account["role"],
                },
            })

            user_id = auth_response.user.id
            print(f"  Auth user created: {user_id}")

        except Exception as e:
            error_str = str(e)
            if "already been registered" in error_str:
                # User exists in auth but not in sco_users — find their ID
                users = client.auth.admin.list_users()
                user_id = None
                for u in users:
                    if hasattr(u, 'email') and u.email == email:
                        user_id = u.id
                        break
                if not user_id:
                    print(f"  ERROR: User exists in auth but can't find ID: {e}")
                    continue
                print(f"  Auth user already exists: {user_id}")
            else:
                print(f"  ERROR creating auth user: {e}")
                continue

        # Insert into sco_users table
        try:
            sco_response = client.table("sco_users").upsert({
                "id": str(user_id),
                "institution_id": account["institution_id"],
                "email": email,
                "full_name": account["full_name"],
                "role": account["role"],
                "active": True,
            }).execute()

            if sco_response.data:
                print(f"  sco_users record created: {account['role']} @ {account['institution_id']}")
            else:
                print(f"  WARNING: sco_users insert returned no data")

        except Exception as e:
            print(f"  ERROR inserting sco_users: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("TEST ACCOUNTS")
    print("=" * 60)
    print(f"{'Email':<25} {'Role':<12} {'Password'}")
    print("-" * 60)
    for account in TEST_ACCOUNTS:
        print(f"{account['email']:<25} {account['role']:<12} {account['password']}")
    print("\nAll accounts use the same password: AllowED2026!")
    print("=" * 60)


if __name__ == "__main__":
    main()
