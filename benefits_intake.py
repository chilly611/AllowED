"""
VA Benefits Intake — PDF Generation & Upload Pipeline
======================================================
Completes the end-to-end submission chain:
  Decision Tree → EM Fields → Certification PDF → Benefits Intake API Upload

Two modules:
  1. PDF Generator — EMEnrollment → formatted VA certification PDF
  2. Benefits Intake Client — 2-step upload (get URL → PUT PDF)

Authority: SCO Handbook Rev 7.4; VA Benefits Intake API docs
"""

import io
import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)

# Import our pipeline modules
from decision_tree import (
    DecisionTreeOutput, CourseResult, Modality, TrainingTime,
    AcademicLevel, StudentInput, CourseSchedule, GradingBasis,
    run_decision_tree,
)
from em_integration import (
    EMEnrollment, BenefitChapter, SubmissionStatus, TuitionData,
    format_for_em, print_em_enrollment,
)
from va_api_client import APIConfig, load_env, RateLimiter


# ---------------------------------------------------------------------------
# PDF Generator — Certification Document
# ---------------------------------------------------------------------------

def generate_certification_pdf(
    enrollment: EMEnrollment,
    output_path: str = None,
) -> bytes:
    """
    Generate a VA enrollment certification PDF from an EMEnrollment record.

    This is the document that gets uploaded to the Benefits Intake API.
    Formatted to match the data VA expects from SCOs.

    Returns PDF as bytes (also saves to output_path if provided).
    """

    buffer = io.BytesIO()

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
        textColor=colors.HexColor("#1F4E79"),
    )

    heading_style = ParagraphStyle(
        "CertHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor("#1F4E79"),
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

    # Build the document
    story = []

    # --- Header ---
    story.append(Paragraph(
        "VA ENROLLMENT CERTIFICATION", title_style
    ))
    story.append(Paragraph(
        f"Facility Code: {enrollment.facility_code} &bull; "
        f"San Diego State University",
        small_style
    ))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
        small_style
    ))
    story.append(HRFlowable(
        width="100%", thickness=2,
        color=colors.HexColor("#1F4E79"),
        spaceAfter=12,
    ))

    # --- Student Information ---
    story.append(Paragraph("Student Information", heading_style))

    student_data = [
        ["Student Name:", enrollment.student_name],
        ["VA Student ID:", enrollment.student_va_id],
        ["Date of Birth:", str(enrollment.date_of_birth)],
        ["Benefit Chapter:", enrollment.benefit_chapter.value],
        ["Program:", enrollment.program_name],
        ["WEAMS Confidence:", f"{enrollment.weams_match_confidence:.0%}"],
    ]

    student_table = Table(student_data, colWidths=[2 * inch, 4.5 * inch])
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

    # --- Enrollment Period ---
    story.append(Paragraph("Enrollment Period", heading_style))

    period_data = [
        ["Pre-set ID:", enrollment.pre_set_id],
        ["Begin Date:", str(enrollment.begin_date) if enrollment.begin_date else "N/A"],
        ["End Date:", str(enrollment.end_date) if enrollment.end_date else "N/A"],
    ]
    if enrollment.expected_grad_date:
        period_data.append([
            "Expected Graduation:", str(enrollment.expected_grad_date)
        ])

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

    # --- Credit Hours ---
    story.append(Paragraph("Credit Hours", heading_style))

    total_credits = enrollment.resident_credits + enrollment.distance_credits

    credit_data = [
        ["Type", "Credits"],
        ["Residential", f"{enrollment.resident_credits:.1f}"],
        ["Distance", f"{enrollment.distance_credits:.1f}"],
        ["Remedial/Deficiency", f"{enrollment.remedial_credits:.1f}"],
        ["Clock Hours", f"{enrollment.clock_hours:.1f}"],
        ["Total Certifiable", f"{total_credits:.1f}"],
    ]

    credit_table = Table(credit_data, colWidths=[3.25 * inch, 3.25 * inch])
    credit_table.setStyle(TableStyle([
        # Header row
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        # Data rows
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        # Total row bold
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8ECF1")),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
        # Alternating rows
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F5F7FA")),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#F5F7FA")),
    ]))
    story.append(credit_table)

    # --- Training Time ---
    story.append(Paragraph("Training Time", heading_style))

    training_data = [
        ["Training Time:", enrollment.training_time],
        ["Rate of Pursuit:", f"{enrollment.rate_of_pursuit:.0%}"],
        ["MHA Eligible:", "Yes" if enrollment.mha_eligible else "No"],
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

    # --- Tuition ---
    if enrollment.tuition:
        story.append(Paragraph("Tuition and Fees", heading_style))
        t = enrollment.tuition

        tuition_data = [
            ["Item", "Amount"],
            ["Gross Tuition", f"${t.gross_tuition:,.2f}"],
        ]
        if t.chapter_rule == "net":
            tuition_data.append(["Aid/Scholarships", f"-${t.aid_amount:,.2f}"])
            tuition_data.append(["Net Tuition", f"${t.net_tuition:,.2f}"])
        tuition_data.append([
            f"Reported to VA ({t.chapter_rule.upper()})",
            f"${t.reported_tuition:,.2f}"
        ])

        tuition_table = Table(tuition_data, colWidths=[3.25 * inch, 3.25 * inch])
        tuition_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8ECF1")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
        ]))
        story.append(tuition_table)

    # --- Course Detail (Audit Trail) ---
    story.append(Paragraph("Course Detail", heading_style))

    course_header = ["Course", "Units", "Certifiable", "Modality", "Reason"]
    course_rows = [course_header]

    for cd in enrollment.course_details:
        cert = "Yes" if cd["certifiable"] else "No"
        mod = (cd["modality"] or "—").capitalize()
        reason = ""
        if not cd["certifiable"] and cd["exclusion_reason"]:
            reason = cd["exclusion_reason"]
        elif cd["certifiable"] and cd["flags"]:
            reason = cd["flags"][0][:40]

        course_rows.append([
            cd["course_id"],
            f"{cd['units']:.1f}",
            cert,
            mod,
            reason[:45],
        ])

    course_table = Table(
        course_rows,
        colWidths=[1.1 * inch, 0.6 * inch, 0.8 * inch, 1.0 * inch, 3.0 * inch],
    )
    course_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (2, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
        # Alternating row shading
        *[("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F7FA"))
          for i in range(1, len(course_rows), 2)],
    ]))
    story.append(course_table)

    # --- Certification Statement ---
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
        "student's Degree Audit Report (DARS) and the institution's records "
        "in PeopleSoft Campus Solutions.",
        normal_style,
    ))

    story.append(Spacer(1, 20))

    sig_data = [
        ["School Certifying Official:", "________________________________"],
        ["Date:", datetime.now().strftime("%B %d, %Y")],
        ["Facility Code:", enrollment.facility_code],
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

    # --- Audit Trail Note ---
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f"<i>{enrollment.notes}</i>",
        small_style,
    ))

    # Build the PDF
    doc.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    # Save to file if path provided
    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

    return pdf_bytes


# ---------------------------------------------------------------------------
# Benefits Intake API Client — 2-Step Upload
# ---------------------------------------------------------------------------

class BenefitsIntakeClient:
    """
    VA Lighthouse Benefits Intake API — 2-step document upload.

    Step 1: POST /uploads → get upload URL + GUID
    Step 2: PUT document to the upload URL

    Then poll GET /uploads/{id} for processing status.

    Sandbox: https://sandbox-api.va.gov/services/vba_documents/v1
    Production: https://api.va.gov/services/vba_documents/v1
    """

    SANDBOX_URL = "https://sandbox-api.va.gov/services/vba_documents/v1"
    PRODUCTION_URL = "https://api.va.gov/services/vba_documents/v1"

    def __init__(self, config: APIConfig, mode: str = "sandbox"):
        self.mode = mode
        self.config = config

        if mode == "sandbox":
            self.base_url = self.SANDBOX_URL
            self.api_key = config.benefits_intake_sandbox_key
        elif mode == "production":
            self.base_url = self.PRODUCTION_URL
            self.api_key = config.benefits_intake_prod_key
        else:
            raise ValueError(f"Invalid mode: {mode}")

        if not self.api_key:
            raise ValueError(
                f"No Benefits Intake API key for mode '{mode}'. Check .env file."
            )

        self.rate_limiter = RateLimiter()
        self.upload_log: list[dict] = []

    def _headers(self) -> dict:
        return {"apikey": self.api_key}

    def request_upload_url(self) -> dict:
        """
        Step 1: Request an upload URL from VA.

        POST /uploads → returns GUID + pre-signed upload URL.

        Returns:
            {
                "success": True/False,
                "guid": "uuid-string",
                "upload_url": "https://...",
                "status": "pending",
            }
        """
        self.rate_limiter.wait_if_needed()

        try:
            r = requests.post(
                f"{self.base_url}/uploads",
                headers={**self._headers(), "Content-Type": "application/json"},
                timeout=30,
            )

            self.rate_limiter.update_from_headers(dict(r.headers))

            if r.status_code in (200, 202):
                data = r.json()["data"]
                result = {
                    "success": True,
                    "guid": data["id"],
                    "upload_url": data["attributes"]["location"],
                    "status": data["attributes"]["status"],
                    "rate_remaining": self.rate_limiter.remaining,
                }
                self.upload_log.append({
                    "step": "request_url",
                    "guid": data["id"],
                    "timestamp": datetime.now().isoformat(),
                    "status_code": r.status_code,
                })
                return result
            else:
                return {
                    "success": False,
                    "error": f"HTTP {r.status_code}: {r.text[:200]}",
                    "rate_remaining": self.rate_limiter.remaining,
                }

        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def upload_document(
        self,
        upload_url: str,
        guid: str,
        pdf_bytes: bytes,
        metadata: dict,
    ) -> dict:
        """
        Step 2: Upload the PDF document to the pre-signed URL.

        Uses multipart/form-data with:
          - "metadata" part: JSON with veteran info
          - "content" part: the PDF file

        Returns:
            {"success": True/False, "guid": "...", "message": "..."}
        """
        self.rate_limiter.wait_if_needed()

        # Build multipart form data
        # Benefits Intake API expects metadata as JSON and content as file
        metadata_json = json.dumps(metadata)

        files = {
            "metadata": (
                "metadata.json",
                metadata_json,
                "application/json",
            ),
            "content": (
                "certification.pdf",
                pdf_bytes,
                "application/pdf",
            ),
        }

        try:
            r = requests.put(
                upload_url,
                files=files,
                headers={"apikey": self.api_key},
                timeout=60,
            )

            self.rate_limiter.update_from_headers(dict(r.headers))

            self.upload_log.append({
                "step": "upload_document",
                "guid": guid,
                "timestamp": datetime.now().isoformat(),
                "status_code": r.status_code,
                "size_bytes": len(pdf_bytes),
            })

            if r.status_code in (200, 202):
                return {
                    "success": True,
                    "guid": guid,
                    "message": "Document uploaded successfully.",
                    "rate_remaining": self.rate_limiter.remaining,
                }
            else:
                return {
                    "success": False,
                    "guid": guid,
                    "error": f"HTTP {r.status_code}: {r.text[:300]}",
                    "rate_remaining": self.rate_limiter.remaining,
                }

        except requests.exceptions.RequestException as e:
            return {"success": False, "guid": guid, "error": str(e)}

    def check_status(self, guid: str) -> dict:
        """
        Poll the status of a submitted document.

        GET /uploads/{guid}

        Statuses: pending → uploaded → received → processing → success/error
        """
        self.rate_limiter.wait_if_needed()

        try:
            r = requests.get(
                f"{self.base_url}/uploads/{guid}",
                headers=self._headers(),
                timeout=30,
            )

            self.rate_limiter.update_from_headers(dict(r.headers))

            if r.status_code == 200:
                data = r.json()["data"]
                attrs = data["attributes"]
                return {
                    "success": True,
                    "guid": guid,
                    "status": attrs["status"],
                    "detail": attrs.get("detail", ""),
                    "code": attrs.get("code"),
                    "updated_at": attrs.get("updated_at", ""),
                }
            else:
                return {
                    "success": False,
                    "guid": guid,
                    "error": f"HTTP {r.status_code}: {r.text[:200]}",
                }

        except requests.exceptions.RequestException as e:
            return {"success": False, "guid": guid, "error": str(e)}

    def submit_certification(
        self,
        enrollment: EMEnrollment,
        pdf_bytes: bytes,
    ) -> dict:
        """
        Full 2-step submission: request URL → upload PDF.

        This is the main method for submitting a certification.

        Returns:
            {
                "success": True/False,
                "guid": "...",
                "message": "...",
                "status_url": "/uploads/{guid}",
            }
        """

        # Step 1: Get upload URL
        print("    Step 1: Requesting upload URL from VA...")
        url_result = self.request_upload_url()

        if not url_result["success"]:
            return {
                "success": False,
                "error": f"Step 1 failed: {url_result.get('error', 'Unknown')}",
            }

        guid = url_result["guid"]
        upload_url = url_result["upload_url"]
        print(f"    Got GUID: {guid}")
        print(f"    Rate remaining: {url_result['rate_remaining']}/60")

        # Build metadata for the upload
        metadata = {
            "veteranFirstName": enrollment.student_name.split(", ")[-1] if ", " in enrollment.student_name else enrollment.student_name,
            "veteranLastName": enrollment.student_name.split(", ")[0] if ", " in enrollment.student_name else "",
            "source": "SDSU VA Certification Automation",
            "docType": "21-1999",  # VA Form for enrollment certification
            "businessLine": "EDU",
            "fileNumber": enrollment.student_va_id.replace("*", "").replace("-", ""),
        }

        # Step 2: Upload the PDF
        print("    Step 2: Uploading certification PDF...")
        upload_result = self.upload_document(
            upload_url=upload_url,
            guid=guid,
            pdf_bytes=pdf_bytes,
            metadata=metadata,
        )

        if upload_result["success"]:
            print(f"    Upload complete. GUID: {guid}")
            return {
                "success": True,
                "guid": guid,
                "message": "Certification PDF uploaded to VA Benefits Intake.",
                "status_url": f"/uploads/{guid}",
                "rate_remaining": upload_result["rate_remaining"],
            }
        else:
            return {
                "success": False,
                "guid": guid,
                "error": f"Step 2 failed: {upload_result.get('error', 'Unknown')}",
            }


# ---------------------------------------------------------------------------
# Full Pipeline Test — James Roster End-to-End
# ---------------------------------------------------------------------------

def james_roster_full_pipeline():
    """
    Complete end-to-end test:
      Decision Tree → EM Fields → Certification PDF → Benefits Intake API Upload

    Uses the live VA sandbox.
    """

    print("=" * 70)
    print("  FULL PIPELINE: DECISION TREE → PDF → VA SUBMISSION")
    print("=" * 70)

    # -------------------------------------------------------------------
    # Step 1: Decision Tree
    # -------------------------------------------------------------------
    print("\n>>> Step 1: Run Decision Tree\n")

    student = StudentInput(
        name="Daniel Bahena",
        student_id="NF-001",
        program="B.A. Journalism",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2024",
        courses=[
            CourseSchedule(
                course_id="ENS 331", title="Environmental Science",
                units=3.0, grading_basis=GradingBasis.LETTER,
                in_dars=False, all_online=True, has_in_person_session=False,
            ),
            CourseSchedule(
                course_id="MIS 401", title="Management Information Systems",
                units=3.0, grading_basis=GradingBasis.LETTER,
                in_dars=True, dars_rationale="major requirement",
                all_online=False, has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="MIS 460", title="Business Application Development",
                units=3.0, grading_basis=GradingBasis.LETTER,
                in_dars=True, dars_rationale="major requirement",
                all_online=False, has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="MIS 585", title="Electronic Commerce Strategy",
                units=3.0, grading_basis=GradingBasis.LETTER,
                in_dars=True, dars_rationale="major requirement",
                all_online=True, has_in_person_session=False,
            ),
            CourseSchedule(
                course_id="MUSIC 151", title="Introduction to Music",
                units=3.0, grading_basis=GradingBasis.LETTER,
                in_dars=True, dars_rationale="GE area",
                all_online=True, has_in_person_session=False,
            ),
        ],
    )

    dt_output = run_decision_tree(student)
    print(f"  Decision Tree: R:{dt_output.residential_units:.0f} "
          f"D:{dt_output.distance_units:.0f} "
          f"T:{dt_output.total_certifiable_units:.0f}")
    print(f"  ENS 331 excluded: {not any(r.certifiable for r in dt_output.course_results if r.course_id == 'ENS 331')}")

    # -------------------------------------------------------------------
    # Step 2: Format for EM
    # -------------------------------------------------------------------
    print("\n>>> Step 2: Format for Enrollment Manager\n")

    enrollment = format_for_em(
        dt_output=dt_output,
        student_va_id="***-**-1234",
        student_dob=date(1998, 3, 15),
        facility_code="11910105",
        pre_set_id="Fall-2024",
        term_start=date(2024, 8, 21),
        term_end=date(2024, 12, 11),
        gross_tuition=3898.00,
        aid_amount=1200.00,
        weams_confidence=0.98,
    )

    print(f"  Status: {enrollment.status.value}")
    print(f"  R:{enrollment.resident_credits:.0f} D:{enrollment.distance_credits:.0f}")
    print(f"  Tuition: ${enrollment.tuition.reported_tuition:,.2f} ({enrollment.tuition.chapter_rule})")

    # -------------------------------------------------------------------
    # Step 3: Generate PDF
    # -------------------------------------------------------------------
    print("\n>>> Step 3: Generate Certification PDF\n")

    pdf_path = "/sessions/friendly-bold-galileo/mnt/VA Project/Nick_Foster_Certification.pdf"
    pdf_bytes = generate_certification_pdf(enrollment, output_path=pdf_path)

    print(f"  PDF generated: {len(pdf_bytes):,} bytes")
    print(f"  Saved to: {pdf_path}")

    # -------------------------------------------------------------------
    # Step 4: Upload to VA Benefits Intake (Sandbox)
    # -------------------------------------------------------------------
    print("\n>>> Step 4: Submit to VA Benefits Intake API (Sandbox)\n")

    config = APIConfig.from_env()

    if not config.benefits_intake_sandbox_key:
        print("  SKIPPED: No Benefits Intake sandbox key in .env")
        return

    client = BenefitsIntakeClient(config, mode="sandbox")
    result = client.submit_certification(enrollment, pdf_bytes)

    if result["success"]:
        print(f"\n  SUBMISSION SUCCESSFUL")
        print(f"    GUID: {result['guid']}")
        print(f"    Message: {result['message']}")
        print(f"    Rate remaining: {result.get('rate_remaining', 'N/A')}/60")

        # Check status
        print("\n>>> Step 5: Check Submission Status\n")
        status = client.check_status(result["guid"])
        print(f"    Status: {status.get('status', 'unknown')}")
        print(f"    Detail: {status.get('detail', 'N/A')}")
    else:
        print(f"\n  SUBMISSION RESULT: {result.get('error', 'Unknown error')}")
        if result.get("guid"):
            print(f"    GUID: {result['guid']}")

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  PIPELINE SUMMARY")
    print("=" * 70)
    print(f"  Decision Tree:  R:{dt_output.residential_units:.0f} "
          f"D:{dt_output.distance_units:.0f} T:{dt_output.total_certifiable_units:.0f}")
    print(f"  EM Formatting:  {enrollment.status.value}")
    print(f"  PDF Generated:  {len(pdf_bytes):,} bytes")
    print(f"  VA Submission:  {'SUCCESS' if result['success'] else 'See above'}")
    if result.get("guid"):
        print(f"  Tracking GUID:  {result['guid']}")
    print("=" * 70)


if __name__ == "__main__":
    james_roster_full_pipeline()
