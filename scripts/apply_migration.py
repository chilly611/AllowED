#!/usr/bin/env python3
"""
Apply AllowED database migration to Supabase.

Usage (from a machine with PostgreSQL network access):
  1. Set your Supabase DB password in .env as SUPABASE_DB_PASSWORD
  2. Run: python3 scripts/apply_migration.py

OR: Copy the SQL from supabase/migrations/20260418000000_initial_schema.sql
    and paste it into the Supabase Dashboard SQL Editor at:
    https://supabase.com/dashboard/project/cwxkpsnjsxaupncqyojq/sql
"""

import os
import sys

# Try to load .env
try:
    from dotenv import dotenv_values
    config = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    print("pip install python-dotenv first")
    sys.exit(1)

url = config.get("SUPABASE_URL", "")
ref = url.split("//")[1].split(".")[0] if "//" in url else ""

# Try to get DB password (separate from service_role_key)
db_password = config.get("SUPABASE_DB_PASSWORD", "")
if not db_password:
    print("SUPABASE_DB_PASSWORD not set in .env")
    print(f"Find it in: https://supabase.com/dashboard/project/{ref}/settings/database")
    print("\nAlternative: paste the migration SQL into the Dashboard SQL Editor:")
    print(f"  https://supabase.com/dashboard/project/{ref}/sql")
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("pip install psycopg2-binary first")
    sys.exit(1)

# Read migration SQL
migration_path = os.path.join(
    os.path.dirname(__file__), '..', 'supabase', 'migrations',
    '20260418000000_initial_schema.sql'
)
with open(migration_path) as f:
    sql = f.read()

# Connect and execute
conn_str = f"postgresql://postgres.{ref}:{db_password}@aws-0-us-west-2.pooler.supabase.com:5432/postgres"
print(f"Connecting to Supabase project {ref}...")

try:
    conn = psycopg2.connect(conn_str, connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor()

    print("Applying migration...")
    cur.execute(sql)

    # Verify
    cur.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    tables = [row[0] for row in cur.fetchall()]
    print(f"\nMigration complete! {len(tables)} tables created:")
    for t in tables:
        print(f"  - {t}")

    # Check RLS
    cur.execute("""
        SELECT tablename, rowsecurity FROM pg_tables
        WHERE schemaname = 'public' AND rowsecurity = true
        ORDER BY tablename
    """)
    rls_tables = cur.fetchall()
    print(f"\nRLS enabled on {len(rls_tables)} tables")

    cur.close()
    conn.close()
    print("\nDone!")

except Exception as e:
    print(f"Error: {e}")
    print(f"\nIf connection fails, use the Dashboard SQL Editor instead:")
    print(f"  https://supabase.com/dashboard/project/{ref}/sql")
    sys.exit(1)
