#!/usr/bin/env python3
"""
Generate realistic synthetic student cohorts for AllowED testing and validation.

This script:
1. Loads real WEAMS programs for a given institution (or all 25 CSU schools)
2. Generates realistic synthetic students with proper distribution:
   - 200-800 students per school (scale by program_count)
   - 85% Ch.33, 10% Ch.35, 5% Ch.31
   - ~70% undergrad, ~25% master's, ~5% doctoral
3. Creates varied course schedules exercising all decision tree branches:
   - All_online, hybrid, in-person, audit, repeat, remedial, thesis, practicum, DARS gaps
4. Includes canonical "James Roster" test case (Daniel Bahena, SDSU)
5. Runs decision tree on all students and inserts results
6. Prints summary statistics

Usage:
  python3 scripts/generate_synthetic_cohort.py --facility-code 11910105 --term "Fall 2026"
  python3 scripts/generate_synthetic_cohort.py --all --term "Fall 2026"
  python3 scripts/generate_synthetic_cohort.py --facility-code 11910105 --term "Fall 2026" --dry-run
"""

import os
import sys
import json
import random
import argparse
from pathlib import Path
from datetime import date
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

try:
    from dotenv import dotenv_values
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv")
    sys.exit(1)

config = dotenv_values(os.path.join(os.path.dirname(__file__), '..', '.env'))
SUPABASE_URL = config.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = config.get("SUPABASE_SERVICE_ROLE_KEY", "")

try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase-py not installed. Run: pip install supabase")
    sys.exit(1)

# Import decision tree
sys.path.insert(0, os.path.dirname(__file__) + '/..')
try:
    from decision_tree import (
        StudentInput, CourseSchedule, run_decision_tree,
        GradingBasis, AcademicLevel
    )
    from weams_programs import match_weams_program
except ImportError as e:
    print(f"ERROR: Cannot import decision tree modules: {e}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Realistic Data
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "James", "John", "Michael", "Daniel", "David", "Robert", "Richard",
    "Joseph", "Thomas", "Christopher", "Carlos", "Luis", "Miguel", "Juan",
    "Antonio", "Maria", "Jennifer", "Patricia", "Linda", "Barbara",
    "Jessica", "Nancy", "Karen", "Lisa", "Sarah", "Nicole", "Michelle",
    "Angela", "Amy", "Emily", "Sophia", "Elizabeth", "Margaret", "Susan",
    "Dorothy", "Angela", "Brenda", "Donna", "Debra", "Amber", "Sandra",
    "Keisha", "Crystal", "Jasmine", "Aisha", "Latoya", "Anya", "Priya",
    "Mei", "Lin", "Wei", "Yuki", "Sakura", "Arjun", "Ravi", "Ahmed",
    "Ali", "Hassan", "Khalid", "Youssef", "Marcus", "Andre", "DeShawn"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Jones", "Brown", "Davis", "Miller",
    "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White",
    "Harris", "Martin", "Thompson", "Garcia", "Martinez", "Rodriguez",
    "Hernandez", "Lopez", "Gonzalez", "Sanchez", "Chavez", "Ramirez",
    "Torres", "Ortiz", "Gutierrez", "Dominguez", "Castro", "Vargas",
    "Silva", "Santos", "Perez", "Flores", "Romero", "Morales", "Gutierrez",
    "Washington", "Jefferson", "Lincoln", "Grant", "Lee", "Grant", "Sherman",
    "O'Brien", "O'Connor", "Murphy", "Sullivan", "Fitzgerald", "Donnelly",
    "Chen", "Wang", "Wu", "Liu", "Huang", "Yang", "Li", "Zhang", "Xu",
    "Kim", "Park", "Lee", "Choi", "Jung", "Kang", "Cho", "Yoon", "Han",
    "Tanaka", "Suzuki", "Watanabe", "Nakamura", "Kobayashi", "Yamamoto",
    "Patel", "Kumar", "Singh", "Sharma", "Desai", "Verma", "Pillai",
    "Ahmed", "Ali", "Hassan", "Omar", "Ibrahim", "Abdullah", "Hussein"
]

COURSE_PREFIXES = [
    "MIS", "CS", "MATH", "PHYS", "CHEM", "BIO", "ENG", "HIST", "PSYCH",
    "SOC", "ECON", "ACCT", "FIN", "MGMT", "MKT", "COMM", "ART", "MUSIC",
    "THEA", "DANCE", "PE", "EDUC", "NURS", "BUSN", "ENGR", "GEOL", "GEO",
    "ASTR", "ANTH", "PHIL", "RELG", "POLS", "LAW", "ENS", "ENVR", "PENV"
]

COURSE_TITLES = {
    "MIS": ["Management Information Systems", "Business Intelligence Systems",
            "Advanced Data Analytics", "Database Design", "Systems Architecture",
            "IT Project Management", "Network Administration", "Cloud Computing",
            "Enterprise Systems", "Data Warehousing"],
    "CS": ["Introduction to Computer Science", "Data Structures", "Algorithms",
           "Operating Systems", "Databases", "Web Development", "Software Engineering",
           "Computer Networks", "Artificial Intelligence", "Machine Learning"],
    "MATH": ["Calculus I", "Calculus II", "Linear Algebra", "Discrete Mathematics",
             "Differential Equations", "Abstract Algebra", "Topology", "Analysis",
             "Numerical Methods", "Statistics"],
    "ENG": ["English Composition", "Literature and Culture", "Shakespeare",
            "American Literature", "Creative Writing", "Technical Writing",
            "Rhetoric and Composition", "World Literature", "Critical Theory"],
    "PSYCH": ["Introduction to Psychology", "Developmental Psychology",
              "Abnormal Psychology", "Social Psychology", "Cognitive Psychology",
              "Research Methods", "Statistics", "Neuroscience", "Health Psychology"],
    "ENS": ["Environmental Studies", "Sustainability", "Environmental Policy",
            "Ecology", "Climate Change", "Conservation Biology", "Environmental Law"],
    "BUSN": ["Business Law", "Ethics in Business", "Organizational Behavior",
             "Human Resources", "Strategic Management", "Business Analytics"],
}


# ---------------------------------------------------------------------------
# Synthetic Data Generation
# ---------------------------------------------------------------------------

def load_weams_data() -> list:
    """Load weams_all_schools.json."""
    project_root = Path(__file__).parent.parent
    weams_path = project_root / "weams_all_schools.json"
    with open(weams_path, 'r') as f:
        return json.load(f)


def get_school_by_facility_code(schools: list, facility_code: str) -> Optional[dict]:
    """Find school by facility code."""
    for school in schools:
        if school.get("facility_code") == facility_code:
            return school
    return None


def get_student_count(program_count: int) -> int:
    """Scale student count by program count (200-800 per school)."""
    # Small school (100 programs) → 200 students
    # Large school (500 programs) → 700 students
    # Formula: 200 + (program_count / 500) * 500
    count = min(800, max(200, int(200 + (program_count / 500) * 500)))
    return count


def random_dob() -> date:
    """Generate realistic DOB (18-65 years old, typically 18-35 for students)."""
    # Most students are 18-35 years old
    year = random.randint(1991, 2008)
    month = random.randint(1, 12)
    day = random.randint(1, 28)  # Safe for all months
    return date(year, month, day)


def generate_course_schedule(academic_level: str, index: int = 0) -> Dict:
    """
    Generate a single course with realistic modality/grading distributions.
    """
    prefix = random.choice(COURSE_PREFIXES)
    course_id = f"{prefix} {300 + index % 200}"

    titles = COURSE_TITLES.get(prefix, [f"{prefix} Course {index}"])
    title = random.choice(titles)

    units = random.choice([1.0, 1.5, 2.0, 3.0, 4.0, 4.5, 5.0])

    # Grading basis distribution
    grading_roll = random.random()
    if grading_roll < 0.02:  # 2% audit
        grading_basis = "audit"
    elif grading_roll < 0.05:  # 3% CR/NC
        grading_basis = "cr_nc"
    else:  # 95% letter grade
        grading_basis = "letter"

    # In/out of DARS
    in_dars = random.random() > 0.05  # 5% NOT in DARS

    # Modality distribution (of in-person courses)
    modality_roll = random.random()
    if modality_roll < 0.05:  # 5% all_online
        all_online = True
        has_in_person_session = False
    elif modality_roll < 0.15:  # 10% hybrid
        all_online = False
        has_in_person_session = True
    else:  # 80% in-person
        all_online = False
        has_in_person_session = True

    # Remedial (1-2% of courses)
    is_remedial = random.random() < 0.02

    # Repeat (3% of courses, ~2/3 previously passed)
    is_repeat = random.random() < 0.03
    previously_passed = is_repeat and random.random() < 0.66

    # Thesis/practicum (for grad students)
    is_thesis = False
    is_practicum = False
    if academic_level in ("masters", "doctoral"):
        if random.random() < 0.03:  # 3% thesis
            is_thesis = True
            all_online = False
            has_in_person_session = False  # Thesis doesn't have modality

    # Practicum (2% of courses)
    if random.random() < 0.02 and not is_thesis:
        is_practicum = True
        all_online = False
        has_in_person_session = True  # Practicum is always residential

    return {
        "course_id": course_id,
        "title": title,
        "units": units,
        "grading_basis": grading_basis,
        "in_dars": in_dars,
        "has_in_person_session": has_in_person_session,
        "all_online": all_online,
        "is_remedial": is_remedial,
        "is_repeat": is_repeat,
        "previously_passed": previously_passed,
        "is_thesis": is_thesis,
        "is_practicum": is_practicum,
    }


def generate_courses_for_student(academic_level: str, num_courses: int = None) -> List[Dict]:
    """Generate 3-6 courses (9-18 units) for a student."""
    if num_courses is None:
        num_courses = random.randint(3, 6)

    courses = []
    total_units = 0

    for i in range(num_courses):
        course = generate_course_schedule(academic_level, i)
        courses.append(course)
        total_units += course["units"]

    # Ensure we hit the 9-18 unit target reasonably well
    if total_units < 9:
        courses[-1]["units"] += (9 - total_units)
    elif total_units > 18:
        courses[-1]["units"] = max(1.0, courses[-1]["units"] - (total_units - 18))

    return courses


def generate_synthetic_students(
    facility_code: str,
    schools_data: list,
    count: Optional[int] = None
) -> List[Dict]:
    """
    Generate synthetic students for a given institution.
    """
    school = get_school_by_facility_code(schools_data, facility_code)
    if not school:
        raise ValueError(f"Facility code {facility_code} not found in schools data")

    programs = school.get("programs", [])
    if not programs:
        raise ValueError(f"No programs found for {facility_code}")

    if count is None:
        count = get_student_count(school.get("program_count", 200))

    students = []

    for i in range(count):
        # Pick academic level with distribution: 70% UG, 25% Masters, 5% Doctoral
        level_roll = random.random()
        if level_roll < 0.70:
            academic_level = "undergraduate"
        elif level_roll < 0.95:
            academic_level = "masters"
        else:
            academic_level = "doctoral"

        # Pick benefit chapter: 85% Ch33, 10% Ch35, 5% Ch31
        chapter_roll = random.random()
        if chapter_roll < 0.85:
            benefit_chapter = "ch33"
        elif chapter_roll < 0.95:
            benefit_chapter = "ch35"
        else:
            benefit_chapter = "ch31"

        # Generate student data
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        program = random.choice(programs)
        dob = random_dob()

        # Generate courses
        courses = generate_courses_for_student(academic_level)

        students.append({
            "student_id": f"SYN-{facility_code[-5:]}-{i:06d}",  # e.g., SYN-10105-000000
            "emplid": f"{random.randint(100000000, 999999999):09d}",
            "first_name": first_name,
            "last_name": last_name,
            "dob": dob,
            "benefit_chapter": benefit_chapter,
            "program": program,
            "academic_level": academic_level,
            "courses": courses,
        })

    return students


def get_james_roster_canonical() -> Dict:
    """
    Return the canonical James Roster test case.
    This MUST produce: R:6, D:6, T:12, ENS 331 excluded.
    """
    return {
        "student_id": "JR-001",
        "emplid": "000-00-1234",
        "first_name": "Daniel",
        "last_name": "Bahena",
        "dob": date(1998, 3, 15),
        "benefit_chapter": "ch33",
        "program": "BA JOURNALISM",
        "academic_level": "undergraduate",
        "courses": [
            {
                "course_id": "ENS 331",
                "title": "Environmental Studies",
                "units": 3.0,
                "grading_basis": "letter",
                "in_dars": False,
                "has_in_person_session": True,
                "all_online": False,
                "is_remedial": False,
                "is_repeat": False,
                "previously_passed": False,
                "is_thesis": False,
                "is_practicum": False,
            },
            {
                "course_id": "MIS 401",
                "title": "Management Information Systems",
                "units": 3.0,
                "grading_basis": "letter",
                "in_dars": True,
                "has_in_person_session": True,
                "all_online": False,
                "is_remedial": False,
                "is_repeat": False,
                "previously_passed": False,
                "is_thesis": False,
                "is_practicum": False,
            },
            {
                "course_id": "MIS 460",
                "title": "Business Intelligence Systems",
                "units": 3.0,
                "grading_basis": "letter",
                "in_dars": True,
                "has_in_person_session": True,
                "all_online": False,
                "is_remedial": False,
                "is_repeat": False,
                "previously_passed": False,
                "is_thesis": False,
                "is_practicum": False,
            },
            {
                "course_id": "MIS 585",
                "title": "Advanced Data Analytics",
                "units": 3.0,
                "grading_basis": "letter",
                "in_dars": True,
                "has_in_person_session": False,
                "all_online": True,
                "is_remedial": False,
                "is_repeat": False,
                "previously_passed": False,
                "is_thesis": False,
                "is_practicum": False,
            },
            {
                "course_id": "MUSIC 151",
                "title": "Fundamentals of Music Theory",
                "units": 3.0,
                "grading_basis": "letter",
                "in_dars": True,
                "has_in_person_session": False,
                "all_online": True,
                "is_remedial": False,
                "is_repeat": False,
                "previously_passed": False,
                "is_thesis": False,
                "is_practicum": False,
            },
        ]
    }


# ---------------------------------------------------------------------------
# Database Operations
# ---------------------------------------------------------------------------

def insert_students_to_db(client, institution_id: str, students: List[Dict]) -> int:
    """
    Insert students and their enrollments/course schedules to Supabase.
    Returns count of students inserted.
    """
    # First: insert student records
    student_records = []
    for student in students:
        student_records.append({
            "institution_id": institution_id,
            "student_id_internal": student["student_id"],
            "emplid": student["emplid"],
            "first_name": student["first_name"],
            "last_name": student["last_name"],
            "dob": student["dob"].isoformat() if student["dob"] else None,
            "benefit_chapter": student["benefit_chapter"],
            "program": student["program"],
            "academic_level": student["academic_level"],
            "facility_code": institution_id,
            "active": True,
        })

    if not student_records:
        return 0

    try:
        response = client.table("students").upsert(student_records).execute()
        return len(response.data) if response.data else 0
    except Exception as e:
        print(f"Warning: Could not insert students: {e}")
        return 0


def run_decision_trees_and_store(
    client,
    institution_id: str,
    term_name: str,
    students: List[Dict],
) -> Tuple[int, int]:
    """
    Run decision tree for each student and store enrollment results.
    Returns (enrollments_created, hitl_flags_created).
    """
    hitl_count = 0
    enrollments_created = 0

    # Get term ID
    try:
        terms_response = client.table("terms").select("id").eq(
            "institution_id", institution_id
        ).eq("term_name", term_name).execute()

        if not terms_response.data:
            print(f"Warning: Term '{term_name}' not found for {institution_id}")
            return 0, 0

        term_id = terms_response.data[0]["id"]
    except Exception as e:
        print(f"Warning: Could not fetch term: {e}")
        return 0, 0

    # Get student IDs from DB
    try:
        students_response = client.table("students").select("id, student_id_internal").eq(
            "institution_id", institution_id
        ).execute()

        student_id_map = {
            s["student_id_internal"]: s["id"]
            for s in students_response.data
        }
    except Exception as e:
        print(f"Warning: Could not fetch student IDs: {e}")
        return 0, 0

    # Run decision tree for each student
    for student in students:
        internal_id = student["student_id"]
        if internal_id not in student_id_map:
            continue

        student_db_id = student_id_map[internal_id]

        # Build StudentInput for decision tree
        student_input = StudentInput(
            name=f"{student['first_name']} {student['last_name']}",
            student_id=internal_id,
            program=student["program"],
            academic_level=AcademicLevel[student["academic_level"].upper()],
            benefit_chapter=student["benefit_chapter"],
            term=term_name,
            facility_code=institution_id,
            courses=[
                CourseSchedule(
                    course_id=c["course_id"],
                    title=c["title"],
                    units=c["units"],
                    grading_basis=GradingBasis[c["grading_basis"].upper()],
                    in_dars=c["in_dars"],
                    has_in_person_session=c["has_in_person_session"],
                    all_online=c["all_online"],
                    is_remedial=c["is_remedial"],
                    previously_passed=c.get("previously_passed", False),
                    is_practicum=c.get("is_practicum", False),
                )
                for c in student["courses"]
            ]
        )

        # Run decision tree
        try:
            output = run_decision_tree(student_input)
        except Exception as e:
            print(f"Warning: Decision tree failed for {internal_id}: {e}")
            continue

        # Create enrollment record
        enrollment_data = {
            "student_id": student_db_id,
            "term_id": term_id,
            "institution_id": institution_id,
            "status": "pending",
            "residential_units": float(output.residential_units),
            "distance_units": float(output.distance_units),
            "total_certifiable_units": float(output.total_certifiable_units),
            "training_time": output.training_time.value if output.training_time else None,
            "rate_of_pursuit": float(output.rate_of_pursuit),
            "mha_eligible": output.mha_eligible,
            "weams_matched": output.weams_matched,
            "weams_confidence": 95.0,  # Default for synthetic data
            "decision_tree_output": {
                "course_results": [
                    {
                        "course_id": cr.course_id,
                        "title": cr.title,
                        "units": cr.units,
                        "certifiable": cr.certifiable,
                        "modality": cr.modality.value if cr.modality else None,
                        "exclusion_reason": cr.exclusion_reason.value if cr.exclusion_reason else None,
                    }
                    for cr in output.course_results
                ]
            },
        }

        try:
            enroll_response = client.table("enrollments").upsert([enrollment_data]).execute()
            if enroll_response.data:
                enrollments_created += 1
                enrollment_id = enroll_response.data[0]["id"]

                # Insert course schedules
                course_schedules = []
                for course_result in output.course_results:
                    course_schedules.append({
                        "enrollment_id": enrollment_id,
                        "institution_id": institution_id,
                        "course_id": course_result.course_id,
                        "title": course_result.title,
                        "units": course_result.units,
                        "certifiable": course_result.certifiable,
                        "modality": course_result.modality.value if course_result.modality else None,
                        "exclusion_reason": course_result.exclusion_reason.value if course_result.exclusion_reason else None,
                        "step_failed": course_result.step_failed,
                    })

                if course_schedules:
                    client.table("course_schedules").insert(course_schedules).execute()

                # Check for HITL triggers
                if len(output.sco_queue_items) > 0 or output.rate_of_pursuit < 0.5:
                    hitl_count += 1
        except Exception as e:
            print(f"Warning: Could not insert enrollment for {internal_id}: {e}")

    return enrollments_created, hitl_count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic student cohorts for AllowED testing"
    )
    parser.add_argument(
        "--facility-code",
        help="Facility code for specific school (e.g., 11910105)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate for all 25 CSU schools"
    )
    parser.add_argument(
        "--term",
        default="Fall 2026",
        help="Term name (default: Fall 2026)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing to database"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("AllowED Synthetic Cohort Generator")
    print("=" * 70)

    # Load schools data
    print("\nLoading WEAMS data...")
    schools = load_weams_data()
    print(f"✓ Loaded {len(schools)} schools")

    # Determine which schools to generate for
    if args.all:
        target_schools = schools
    elif args.facility_code:
        school = get_school_by_facility_code(schools, args.facility_code)
        if not school:
            print(f"ERROR: Facility code {args.facility_code} not found")
            sys.exit(1)
        target_schools = [school]
    else:
        parser.print_help()
        sys.exit(1)

    # Create client (unless dry-run)
    client = None
    if not args.dry_run:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
            sys.exit(1)

        print("Connecting to Supabase...")
        try:
            client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            response = client.table("students").select("*").limit(1).execute()
            print("✓ Connected to Supabase")
        except Exception as e:
            print(f"✗ Cannot connect to Supabase: {e}")
            sys.exit(1)

    # Generate and insert for each school
    total_students = 0
    total_enrollments = 0
    total_hitl = 0
    chapter_distribution = defaultdict(int)

    for school in target_schools:
        facility_code = school.get("facility_code", "")
        school_name = school.get("school", facility_code)

        print(f"\n--- {school_name} ({facility_code}) ---")

        # Generate students
        try:
            students = generate_synthetic_students(facility_code, schools)

            # Add canonical James Roster for SDSU
            if facility_code == "11910105":
                james = get_james_roster_canonical()
                students.insert(0, james)  # Put at front for easy testing
                print(f"✓ Added canonical James Roster (Daniel Bahena)")

            print(f"Generated {len(students)} students")

            # Track chapters
            for s in students:
                chapter_distribution[s["benefit_chapter"]] += 1

            if args.dry_run:
                print(f"[DRY RUN] Would insert {len(students)} students")
                total_students += len(students)
                continue

            # Insert to DB
            student_count = insert_students_to_db(client, facility_code, students)
            print(f"✓ Inserted {student_count} students")

            # Run decision trees
            enroll_count, hitl_count = run_decision_trees_and_store(
                client, facility_code, args.term, students
            )
            print(f"✓ Created {enroll_count} enrollments, {hitl_count} HITL flags")

            total_students += student_count
            total_enrollments += enroll_count
            total_hitl += hitl_count

        except Exception as e:
            print(f"✗ Error processing {school_name}: {e}")
            continue

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Schools processed:    {len(target_schools)}")
    print(f"Total students:       {total_students}")
    print(f"Total enrollments:    {total_enrollments}")
    print(f"HITL flags:           {total_hitl}")

    print("\nBenefit chapter distribution:")
    for chapter in ["ch33", "ch35", "ch31"]:
        count = chapter_distribution[chapter]
        pct = (count / total_students * 100) if total_students > 0 else 0
        print(f"  {chapter:6} {count:5} ({pct:5.1f}%)")

    if args.dry_run:
        print("\n[DRY RUN] No changes made")
    else:
        print("\n✓ Generation complete!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
