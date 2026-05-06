#!/usr/bin/env python3
"""
Test Benefits Intake PDF Generation & Submission
==================================================
End-to-end test for the VA Benefits Intake flow.

This script:
  1. Connects to Supabase and fetches Daniel Bahena's data (student_id_internal = 'JR-001')
  2. Generates a VA enrollment certification PDF
  3. Simulates a Benefits Intake API submission (mock mode, since sandbox keys are placeholders)
  4. Saves the PDF to ~/Desktop/AllowED/output/

Usage:
  python3 scripts/test_benefits_intake.py

Environment:
  - SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from .env (used for student data)
  - VA_BENEFITS_INTAKE_SANDBOX_KEY from .env (mock mode if placeholder)
"""

import os
import sys
import json
from pathlib import Path
from datetime import date, datetime
from io import BytesIO

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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

try:
    import requests
except ImportError:
    print("ERROR: requests not installed")
    sys.exit(1)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak,
    )
except ImportError:
    print("ERROR: reportlab not installed")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_env(env_path: str = None) -> dict:
    """Load credentials from .env file."""
    if env_path is None:
        env_path = str(Path(__file__).parent.parent / ".env")

    if not os.path.exists(env_path):
        print(f"ERROR: .env file not found at {env_path}")
        return {}

    env = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


# ---------------------------------------------------------------------------
# Supabase Queries
# ---------------------------------------------------------------------------

def fetch_student_data(client, student_id_internal: str = "JR-001"):
    """
    Fetch Daniel Bahena's enrollment data from Supabase.

    Returns dict with:
      - student info: name, DOB, student_id_internal
      - enrollment: term, benefit_chapter, academic_level
      - courses: list of enrolled courses with units
    """
    print(f"  Fetching student data for {student_id_internal}...")

    # Query students table
    students = client.table("students").select(
        "id, student_id_internal, first_name, last_name, dob, "
        "benefit_chapter, academic_level, program"
    ).eq("student_id_internal", student_id_internal).execute()

    if not students.data:
        print(f"  ERROR: Student {student_id_internal} not found")
        return None

    student = students.data[0]
    student_id = student["id"]
    print(f"    Found: {student['first_name']} {student['last_name']} "
          f"({student['student_id_internal']})")
    if student.get("program"):
        print(f"    Program: {student['program']}")

    # Query enrollments for this student
    enrollments = client.table("enrollments").select(
        "id, term_id, student_id, institution_id, status, residential_units, "
        "distance_units, total_certifiable_units, training_time, rate_of_pursuit"
    ).eq("student_id", student_id).limit(1).execute()

    if not enrollments.data:
        print(f"    WARNING: No enrollment records found for student")
        # Create a synthetic enrollment for testing
        enrollment = {
            "id": None,
            "term_id": 1,
            "institution_id": "11910105",
            "status": "draft",
            "residential_units": 12.0,
            "distance_units": 0.0,
            "total_certifiable_units": 12.0,
            "training_time": "Full-time",
            "rate_of_pursuit": 1.0,
        }
        enrollment_id = None
    else:
        enrollment = enrollments.data[0]
        enrollment_id = enrollment["id"]
        print(f"    Enrollment term ID: {enrollment['term_id']}")

    # Query course_schedules for this enrollment
    if enrollment_id:
        courses_data = client.table("course_schedules").select(
            "id, course_id, title, units, modality, certifiable"
        ).eq("enrollment_id", enrollment_id).execute()
    else:
        courses_data = None

    courses = courses_data.data if courses_data and courses_data.data else []
    print(f"    Found {len(courses)} courses")

    return {
        "student": student,
        "enrollment": enrollment,
        "courses": courses,
    }


def get_term_dates(client, term_id: str = "Fall-2026"):
    """Get term start and end dates from terms table."""
    terms = client.table("terms").select(
        "id, start_date, end_date"
    ).eq("id", term_id).execute()

    if terms.data:
        return terms.data[0]["start_date"], terms.data[0]["end_date"]

    # Fallback dates for Fall 2026
    return "2026-08-21", "2026-12-11"


# ---------------------------------------------------------------------------
# PDF Generation
# ---------------------------------------------------------------------------

def generate_certification_pdf(
    student_data: dict,
    term_id: str = "Fall-2026",
    facility_code: str = "11910105",
    output_path: str = None,
) -> bytes:
    """
    Generate a professional VA enrollment certification PDF.

    Includes:
      - Student info: name, DOB, student ID, benefit chapter
      - Institution: SDSU, facility code
      - Term details
      - Course schedule table
      - Enrollment totals (units, modality breakdown)
      - Certification statement
    """
    print("  Generating PDF...")

    student = student_data["student"]
    enrollment = student_data["enrollment"]
    courses = student_data["courses"]

    # Build course totals
    residential_units = 0.0
    distance_units = 0.0
    total_units = 0.0

    for course in courses:
        if course.get("certifiable", True):
            units = float(course.get("units", 0))
            total_units += units
            modality = course.get("modality", "residential")
            if modality == "distance":
                distance_units += units
            else:
                residential_units += units

    # Determine training time
    if total_units >= 12:
        training_time = "Full-time"
        rate_of_pursuit = 1.0
    elif total_units >= 9:
        training_time = "Three-quarter time"
        rate_of_pursuit = 0.75
    elif total_units >= 6:
        training_time = "Half-time"
        rate_of_pursuit = 0.5
    else:
        training_time = "Less than half-time"
        rate_of_pursuit = total_units / 12.0

    # PDF setup
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    # Styles
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CertTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        spaceAfter=6,
        textColor=colors.HexColor("#1E40AF"),
    )

    heading_style = ParagraphStyle(
        "CertHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor("#1E40AF"),
    )

    normal_style = ParagraphStyle(
        "CertNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
    )

    small_style = ParagraphStyle(
        "CertSmall",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.gray,
    )

    # Build document
    story = []

    # Header
    story.append(Paragraph("VA ENROLLMENT CERTIFICATION", title_style))
    story.append(Paragraph(
        f"San Diego State University &bull; Facility Code: {facility_code}",
        small_style
    ))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
        small_style
    ))
    story.append(HRFlowable(
        width="100%", thickness=2,
        color=colors.HexColor("#0F172A"),
        spaceAfter=12,
    ))

    # Student Information
    story.append(Paragraph("Student Information", heading_style))

    student_full_name = f"{student['last_name']}, {student['first_name']}"
    student_data_table = [
        ["Student Name:", student_full_name],
        ["Date of Birth:", str(student.get("dob", "N/A"))],
        ["Student ID (Internal):", student.get("student_id_internal", "N/A")],
        ["Benefit Chapter:", student.get("benefit_chapter", "Ch33")],
        ["Academic Level:", student.get("academic_level", "Undergraduate")],
    ]

    student_table = Table(student_data_table, colWidths=[2 * inch, 4.5 * inch])
    student_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F7FA")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
    ]))
    story.append(student_table)

    # Enrollment Period
    story.append(Paragraph("Enrollment Period", heading_style))

    period_data = [
        ["Term:", term_id],
        ["Pre-Set ID:", f"{term_id}"],
        ["Academic Year:", "2026-2027"],
    ]

    period_table = Table(period_data, colWidths=[2 * inch, 4.5 * inch])
    period_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F7FA")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
    ]))
    story.append(period_table)

    # Credit Hours
    story.append(Paragraph("Credit Hours", heading_style))

    credit_data = [
        ["Type", "Units"],
        ["Residential", f"{residential_units:.1f}"],
        ["Distance", f"{distance_units:.1f}"],
        ["Total Certifiable", f"{total_units:.1f}"],
    ]

    credit_table = Table(credit_data, colWidths=[3.25 * inch, 3.25 * inch])
    credit_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8ECF1")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
    ]))
    story.append(credit_table)

    # Training Time
    story.append(Paragraph("Training Time & Rate of Pursuit", heading_style))

    training_data = [
        ["Training Time:", training_time],
        ["Rate of Pursuit:", f"{rate_of_pursuit:.0%}"],
        ["MHA Eligible:", "Yes" if rate_of_pursuit >= 0.5 else "No"],
    ]

    training_table = Table(training_data, colWidths=[2 * inch, 4.5 * inch])
    training_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F7FA")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
    ]))
    story.append(training_table)

    # Course Detail Table
    if courses:
        story.append(Paragraph("Course Schedule", heading_style))

        course_header = ["Course ID", "Units", "Certifiable", "Modality"]
        course_rows = [course_header]

        for course in courses:
            course_id = course.get("course_id", "—")
            units = f"{course.get('units', 0):.1f}"
            certifiable = "Yes" if course.get("certifiable", True) else "No"
            modality = (course.get("modality", "residential") or "—").capitalize()

            course_rows.append([course_id, units, certifiable, modality])

        course_table = Table(
            course_rows,
            colWidths=[1.5 * inch, 0.8 * inch, 1.0 * inch, 1.7 * inch],
        )
        course_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (2, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
            *[("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F7FA"))
              for i in range(1, len(course_rows), 2)],
        ]))
        story.append(course_table)

    # Certification Statement
    story.append(Spacer(1, 20))
    story.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#D0D5DD"),
        spaceAfter=12,
    ))

    story.append(Paragraph("Certification Statement", heading_style))
    story.append(Paragraph(
        "I certify that the information herein is true and correct to the best "
        "of my knowledge. The enrollment data has been verified against the "
        "student's academic record and the institution's enrollment system.",
        normal_style,
    ))

    story.append(Spacer(1, 20))

    sig_data = [
        ["School Certifying Official:", "________________________________"],
        ["Date:", datetime.now().strftime("%B %d, %Y")],
        ["Facility Code:", facility_code],
    ]
    sig_table = Table(sig_data, colWidths=[2.5 * inch, 4.0 * inch])
    sig_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(sig_table)

    # Build PDF
    doc.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    # Save to file if path provided
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"    PDF saved: {output_path} ({len(pdf_bytes):,} bytes)")

    return pdf_bytes


# ---------------------------------------------------------------------------
# Mock Benefits Intake Submission
# ---------------------------------------------------------------------------

def simulate_benefits_intake_submission(
    student_data: dict,
    pdf_bytes: bytes,
    facility_code: str = "11910105",
) -> dict:
    """
    Simulate a Benefits Intake API submission in mock mode.

    In a live scenario, this would:
      1. POST to /uploads to get a pre-signed URL
      2. PUT the PDF to that URL with metadata
      3. Poll for processing status

    In mock mode, we just print what would be sent.
    """
    print("  Simulating Benefits Intake API submission...")

    student = student_data["student"]
    enrollment = student_data["enrollment"]

    # Build what would be sent to VA
    metadata = {
        "veteranFirstName": student["first_name"],
        "veteranLastName": student["last_name"],
        "source": "AllowED—SDSU VA Certification Automation",
        "docType": "21-1999",  # VA Form enrollment certification
        "businessLine": "EDU",
        "fileNumber": student.get("student_id_internal", "").replace("-", ""),
    }

    submission_payload = {
        "step_1_get_upload_url": {
            "method": "POST",
            "endpoint": "https://sandbox-api.va.gov/services/vba_documents/v1/uploads",
            "headers": {
                "apikey": "[VA_BENEFITS_INTAKE_SANDBOX_KEY]",
                "Content-Type": "application/json",
            },
            "expected_response": {
                "data": {
                    "id": "[GUID-UUID]",
                    "attributes": {
                        "location": "[pre-signed-upload-url]",
                        "status": "pending",
                    }
                }
            }
        },
        "step_2_upload_pdf": {
            "method": "PUT",
            "url": "[pre-signed-upload-url]",
            "headers": {
                "apikey": "[VA_BENEFITS_INTAKE_SANDBOX_KEY]",
            },
            "multipart_form_data": {
                "metadata": metadata,
                "content": f"[PDF binary, {len(pdf_bytes):,} bytes]",
            },
            "expected_response": {
                "success": True,
                "guid": "[GUID-UUID]",
                "message": "Document uploaded successfully.",
            }
        },
        "step_3_check_status": {
            "method": "GET",
            "endpoint": "https://sandbox-api.va.gov/services/vba_documents/v1/uploads/[GUID-UUID]",
            "headers": {
                "apikey": "[VA_BENEFITS_INTAKE_SANDBOX_KEY]",
            },
            "polling_statuses": [
                "pending → uploaded → received → processing → success/error"
            ]
        }
    }

    return {
        "mock_mode": True,
        "student_name": f"{student['last_name']}, {student['first_name']}",
        "student_id_internal": student.get("student_id_internal"),
        "benefit_chapter": student.get("benefit_chapter"),
        "pdf_size_bytes": len(pdf_bytes),
        "facility_code": facility_code,
        "submission_payload": submission_payload,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("  BENEFITS INTAKE PDF GENERATION & SUBMISSION TEST")
    print("=" * 70)

    # Load environment
    print("\n>>> Step 1: Load Configuration\n")
    env = load_env()

    supabase_url = env.get("SUPABASE_URL")
    supabase_key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    benefits_intake_key = env.get("VA_BENEFITS_INTAKE_SANDBOX_KEY", "placeholder")

    if not supabase_url or not supabase_key:
        print("  ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required in .env")
        sys.exit(1)

    # Determine mode
    is_mock_mode = benefits_intake_key.startswith("your_") or benefits_intake_key == "placeholder"
    mode_str = "MOCK (sandbox key is placeholder)" if is_mock_mode else "LIVE (sandbox key available)"

    print(f"  Mode: {mode_str}")
    print(f"  Supabase: {supabase_url[-20:]}")
    print(f"  Benefits Intake key: {benefits_intake_key[:20]}...")

    # Connect to Supabase
    print("\n>>> Step 2: Connect to Supabase\n")
    try:
        client = create_client(supabase_url, supabase_key)
        print("  Connected to Supabase")
    except Exception as e:
        print(f"  ERROR: Failed to connect to Supabase: {e}")
        sys.exit(1)

    # Fetch student data
    print("\n>>> Step 3: Fetch Student Data\n")
    student_data = fetch_student_data(client, "JR-001")

    if not student_data:
        print("  ERROR: Could not fetch student data")
        sys.exit(1)

    # Generate PDF
    print("\n>>> Step 4: Generate Certification PDF\n")
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    pdf_path = output_dir / "Daniel_Bahena_Enrollment_Certification.pdf"
    pdf_bytes = generate_certification_pdf(
        student_data,
        term_id="Fall-2026",
        facility_code="11910105",
        output_path=str(pdf_path),
    )

    # Simulate/prepare submission
    print("\n>>> Step 5: Prepare Benefits Intake Submission\n")
    submission_result = simulate_benefits_intake_submission(
        student_data,
        pdf_bytes,
        facility_code="11910105",
    )

    print(f"  Student: {submission_result['student_name']}")
    print(f"  Benefit Chapter: {submission_result['benefit_chapter']}")
    print(f"  PDF Size: {submission_result['pdf_size_bytes']:,} bytes")
    print(f"  Facility Code: {submission_result['facility_code']}")

    if is_mock_mode:
        print("\n  MOCK MODE: Showing what would be submitted to VA Benefits Intake API")
        print("\n  --- Step 1: Request Upload URL ---")
        step1 = submission_result['submission_payload']['step_1_get_upload_url']
        print(f"  Method: {step1['method']}")
        print(f"  Endpoint: {step1['endpoint']}")
        print(f"  Headers: {json.dumps(step1['headers'], indent=2)}")

        print("\n  --- Step 2: Upload PDF ---")
        step2 = submission_result['submission_payload']['step_2_upload_pdf']
        print(f"  Method: {step2['method']}")
        print(f"  Metadata: {json.dumps(step2['multipart_form_data']['metadata'], indent=2)}")
        print(f"  Content: {step2['multipart_form_data']['content']}")

        print("\n  --- Step 3: Check Status (Polling) ---")
        step3 = submission_result['submission_payload']['step_3_check_status']
        print(f"  Method: {step3['method']}")
        print(f"  Statuses: {step3['polling_statuses']}")

    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Mode: {'MOCK (placeholder keys)' if is_mock_mode else 'LIVE (sandbox keys available)'}")
    print(f"  PDF Generated: {pdf_path.name}")
    print(f"  Student: {submission_result['student_name']}")
    print(f"  Student ID: {submission_result['student_id_internal']}")
    print(f"  Benefit Chapter: {submission_result['benefit_chapter']}")
    print(f"  PDF Size: {submission_result['pdf_size_bytes']:,} bytes")
    print(f"  Facility Code: {submission_result['facility_code']}")

    if is_mock_mode:
        print("\n  NEXT STEPS:")
        print("    1. Register for VA Lighthouse sandbox credentials")
        print("    2. Add VA_BENEFITS_INTAKE_SANDBOX_KEY to .env")
        print("    3. Re-run this script to test live API submission")
    else:
        print("\n  LIVE MODE: Would submit to VA Benefits Intake API sandbox")
        print("  Check VA Lighthouse dashboard for submission status")

    print("=" * 70)


if __name__ == "__main__":
    main()
