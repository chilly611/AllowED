#!/usr/bin/env python3
"""
Seed AllowED Supabase database with initial institution, program, and term data.

This script:
1. Reads weams_all_schools.json (25 CSU universities with their VA-approved programs)
2. Inserts institutions, WEAMS programs, and creates default Fall 2026 terms
3. Uses idempotent UPSERT logic to handle re-runs safely
4. Prints summary of what was created

Usage:
  python3 scripts/seed.py              # normal seed
  python3 scripts/seed.py --dry-run    # show what would be inserted (no DB writes)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import date
from typing import Optional, Tuple

try:
    from dotenv import dotenv_values
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv")
    sys.exit(1)

# Load environment variables
config = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
SUPABASE_URL = config.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = config.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    print("See .env.example for format")
    sys.exit(1)

# Try to import Supabase client
try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase-py not installed. Run: pip install supabase")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

def load_weams_data() -> list:
    """Load weams_all_schools.json from project root."""
    project_root = Path(__file__).parent.parent
    weams_path = project_root / "weams_all_schools.json"

    if not weams_path.exists():
        print(f"ERROR: {weams_path} not found")
        sys.exit(1)

    with open(weams_path, 'r') as f:
        return json.load(f)


def extract_degree_type(program_name: str) -> Optional[str]:
    """
    Extract degree type from WEAMS program name.

    Examples:
      "BA JOURNALISM" → "BA"
      "BS BIOLOGY" → "BS"
      "MS COMPUTER SCIENCE" → "MS"
      "PHD MATHEMATICS" → "PHD"
      "AUD AUDIOLOGY" → "AUD"
      "ARTICULATION AGREEMENT FOR TRANSFER" → None
    """
    parts = program_name.split()
    if not parts:
        return None

    prefix = parts[0].upper()

    # Common degree types
    if prefix in ("BA", "BS", "BFA", "BM", "BAT", "BS", "MA", "MS", "MBA",
                   "MFA", "MM", "MSW", "MPH", "MPA", "MEng", "PHD", "EdD",
                   "DMA", "MD", "DPT", "AUD", "DDS", "JD"):
        return prefix

    # Check 3-letter combinations
    if len(prefix) == 3 and prefix not in ("AUD",):
        # Could be a degree like "MSW"
        return prefix if any(char in prefix for char in "ABMPS") else None

    # No identifiable degree prefix
    return None


# ---------------------------------------------------------------------------
# Supabase Operations
# ---------------------------------------------------------------------------

def create_supabase_client():
    """Create authenticated Supabase client with service role."""
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return client


def seed_institutions(client, schools_data: list, dry_run: bool = False) -> Tuple[int, dict]:
    """
    Insert institutions (one per school) using UPSERT.
    Returns (count_created, details_dict).
    """
    institutions = []

    for school in schools_data:
        facility_code = school.get("facility_code", "")
        name = school.get("school", "")

        if not facility_code or not name:
            continue

        institutions.append({
            "facility_code": facility_code,
            "name": name,
            "active": True,
        })

    if dry_run:
        print(f"\n[DRY RUN] Would insert {len(institutions)} institutions:")
        for inst in institutions:
            print(f"  {inst['facility_code']:12} {inst['name']}")
        return len(institutions), {"dry_run": True}

    if not institutions:
        return 0, {}

    try:
        # Use upsert to handle re-runs
        response = client.table("institutions").upsert(institutions).execute()
        count = len(response.data) if response.data else 0
        print(f"✓ Seeded {count} institutions")
        return count, {}
    except Exception as e:
        print(f"✗ Error seeding institutions: {e}")
        raise


def seed_weams_programs(client, schools_data: list, dry_run: bool = False) -> Tuple[int, dict]:
    """
    Insert WEAMS programs from each school's program list.
    Returns (count_created, details_dict).
    """
    programs = []
    total_programs = 0

    for school in schools_data:
        facility_code = school.get("facility_code", "")
        school_programs = school.get("programs", [])

        if not facility_code:
            continue

        for program_name in school_programs:
            degree_type = extract_degree_type(program_name)
            programs.append({
                "institution_id": facility_code,
                "program_name": program_name,
                "degree_type": degree_type,
                "approved": True,
            })
            total_programs += 1

    if dry_run:
        print(f"\n[DRY RUN] Would insert {total_programs} programs")
        return total_programs, {}

    if not programs:
        return 0, {}

    try:
        # Batch insert in chunks to avoid timeouts
        chunk_size = 100
        inserted = 0

        for i in range(0, len(programs), chunk_size):
            chunk = programs[i:i+chunk_size]
            response = client.table("weams_programs").upsert(chunk).execute()
            inserted += len(response.data) if response.data else 0

        print(f"✓ Seeded {inserted} WEAMS programs")
        return inserted, {}
    except Exception as e:
        print(f"✗ Error seeding WEAMS programs: {e}")
        raise


def seed_terms(client, schools_data: list, dry_run: bool = False) -> Tuple[int, dict]:
    """
    Create default Fall 2026 term for each institution.
    Dates:
      begin_date: 2026-08-24 (typical CSU semester start)
      end_date: 2026-12-11 (typical fall semester end)
      add_drop_deadline: 2026-09-04 (10 days after start)
      census_date: 2026-09-21 (28 days after start)
      withdrawal_deadline: 2026-11-01 (70 days after start)

    Returns (count_created, details_dict).
    """
    terms = []

    for school in schools_data:
        facility_code = school.get("facility_code", "")

        if not facility_code:
            continue

        terms.append({
            "institution_id": facility_code,
            "term_name": "Fall 2026",
            "begin_date": date(2026, 8, 24),
            "end_date": date(2026, 12, 11),
            "add_drop_deadline": date(2026, 9, 4),
            "census_date": date(2026, 9, 21),
            "withdrawal_deadline": date(2026, 11, 1),
            "active": True,
        })

    if dry_run:
        print(f"\n[DRY RUN] Would insert {len(terms)} terms (Fall 2026)")
        return len(terms), {}

    if not terms:
        return 0, {}

    try:
        # Use upsert to handle re-runs (keyed on institution_id + term_name)
        response = client.table("terms").upsert(terms).execute()
        count = len(response.data) if response.data else 0
        print(f"✓ Seeded {count} Fall 2026 terms")
        return count, {}
    except Exception as e:
        print(f"✗ Error seeding terms: {e}")
        raise


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Seed AllowED database with institutions, programs, and terms"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be inserted without writing to database"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("AllowED Database Seeding Script")
    print("=" * 70)

    # Load data
    print("\nLoading weams_all_schools.json...")
    schools = load_weams_data()
    print(f"✓ Loaded {len(schools)} schools")

    if args.dry_run:
        print("\n[DRY RUN MODE — No database writes]")

    # Create client only if not dry run
    if not args.dry_run:
        print("\nConnecting to Supabase...")
        try:
            client = create_supabase_client()
            # Quick health check
            response = client.table("institutions").select("*").limit(1).execute()
            print("✓ Connected to Supabase")
        except Exception as e:
            print(f"✗ Cannot connect to Supabase: {e}")
            print("\nNote: If schema hasn't been applied yet, run:")
            print("  python3 scripts/apply_migration.py")
            sys.exit(1)
    else:
        client = None

    # Seed data
    try:
        inst_count, _ = seed_institutions(client, schools, dry_run=args.dry_run)
        prog_count, _ = seed_weams_programs(client, schools, dry_run=args.dry_run)
        term_count, _ = seed_terms(client, schools, dry_run=args.dry_run)
    except Exception as e:
        print(f"\n✗ Seeding failed: {e}")
        sys.exit(1)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Institutions:    {inst_count}")
    print(f"WEAMS Programs:  {prog_count}")
    print(f"Terms:           {term_count}")

    if not args.dry_run:
        print("\n✓ Seeding complete!")
    else:
        print("\n[DRY RUN] No changes made")

    return 0


if __name__ == "__main__":
    sys.exit(main())
