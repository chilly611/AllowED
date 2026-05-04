"""
VA Enrollment Manager Integration — Phase 2
=============================================
Takes Decision Tree output and produces EM-ready enrollment data,
then formats it as a Lighthouse API payload for submission.

Two modules:
  1. EM Field Formatter — DecisionTreeOutput → EMEnrollment data structure
  2. Lighthouse API Client — EMEnrollment → API payload, with mock/sandbox mode

Authority: SCO Handbook Rev 7.4; EM Field Mapping F4 v1; Technical Integration Spec v1
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional

# Import the Decision Tree engine
from decision_tree import (
    DecisionTreeOutput, CourseResult, Modality, TrainingTime,
    AcademicLevel, StudentInput, CourseSchedule, GradingBasis,
    run_decision_tree, print_results,
)


# ---------------------------------------------------------------------------
# Enums for EM fields
# ---------------------------------------------------------------------------

class BenefitChapter(Enum):
    CH33 = "Chapter 33 (Post-9/11 GI Bill)"
    CH35 = "Chapter 35 (DEA)"
    CH31 = "Chapter 31 (VR&E)"


class AmendmentReason(Enum):
    TUITION_CHANGE = "Change to Tuition and Fees"
    PRE_REG_REDUCED = "Pre-registered but reduced"
    NEVER_ATTENDED = "Pre-registered but never attended"
    WITHDREW_DROP = "Withdrew during drop period"
    GRADUATED = "Graduated/Received Diploma"


class SubmissionStatus(Enum):
    READY = "ready"             # All validations passed, can submit
    DRAFT = "draft"             # Needs SCO review before submission
    SUBMITTED = "submitted"     # Sent to VA
    AMENDMENT = "amendment"     # Amendment pending
    REJECTED = "rejected"       # VA rejected


class HITLReason(Enum):
    LOW_CONFIDENCE = "Confidence score below 90%"
    ROUNDING_OUT = "Rounding-out scenario detected"
    CUSTOM_REMARK = "Custom remark required"
    FACILITY_MISMATCH = "Facility mismatch"
    WEAMS_LOW_CONFIDENCE = "WEAMS crosswalk confidence below 95%"
    TUITION_DISCREPANCY = "Net tuition discrepancy > 5%"
    AID_SETUP_INCOMPLETE = "Aid setup incomplete in SSR_VB_TF_SETUP"
    SCO_QUEUE_COURSES = "Courses in SCO exception queue"


# ---------------------------------------------------------------------------
# Data classes for EM enrollment
# ---------------------------------------------------------------------------

@dataclass
class PreSetEnrollment:
    """EM Pre-Set Enrollment — one per term, shared across all students."""
    pre_set_id: str              # e.g. "Fall-2026"
    facility_code: str           # "11910105" for SDSU
    term_start_date: date
    term_end_date: date
    vacation_periods: list = field(default_factory=list)
    active: bool = True


@dataclass
class TuitionData:
    """Tuition information for EM submission."""
    gross_tuition: float         # From TUITION_CALC_TBL
    aid_amount: float = 0.0      # From SSR_VB_TF_SETUP (tuition-designated only)
    net_tuition: float = 0.0     # Ch.33: gross - aid. Non-Ch.33: not used
    reported_tuition: float = 0.0  # What actually goes to EM
    chapter_rule: str = ""       # "net" or "gross"


@dataclass
class EMEnrollment:
    """
    Complete EM enrollment record — everything needed for one student-term submission.
    Produced by the EM Field Formatter from Decision Tree output.
    """
    # Student identification
    student_va_id: str           # SSN or ICN — maps to VA file number
    student_name: str            # "LastName, FirstName" format
    date_of_birth: date

    # Program info
    facility_code: str           # WEAMS facility code (11910105 for SDSU)
    benefit_chapter: BenefitChapter
    program_name: str            # WEAMS program name
    weams_match_confidence: float = 1.0  # 0.0–1.0

    # Enrollment period
    pre_set_id: str = ""
    begin_date: Optional[date] = None
    end_date: Optional[date] = None
    expected_grad_date: Optional[date] = None

    # Credits — from Decision Tree Steps 5-6
    resident_credits: float = 0.0
    distance_credits: float = 0.0
    clock_hours: float = 0.0
    remedial_credits: float = 0.0

    # Training time — from Decision Tree Step 7
    training_time: str = ""
    rate_of_pursuit: float = 0.0
    mha_eligible: bool = False

    # Tuition
    tuition: Optional[TuitionData] = None

    # Remarks & notes
    vba_remarks: list = field(default_factory=list)     # Standard VBA remark codes
    custom_remarks: str = ""                             # Free text (triggers HITL)
    notes: str = ""                                      # Internal audit trail

    # Submission control
    status: SubmissionStatus = SubmissionStatus.READY
    hitl_reasons: list = field(default_factory=list)     # Why it's in DRAFT
    confidence_score: float = 1.0                        # 0.0–1.0 overall

    # Course-level detail (for audit trail, not submitted to VA)
    course_details: list = field(default_factory=list)

    # Amendment fields (only populated for amendments)
    is_amendment: bool = False
    amendment_reason: Optional[AmendmentReason] = None
    amendment_effective_date: Optional[date] = None
    is_graduation: bool = False
    is_termination: bool = False


# ---------------------------------------------------------------------------
# EM Field Formatter
# ---------------------------------------------------------------------------

def format_for_em(
    dt_output: DecisionTreeOutput,
    student_va_id: str,
    student_dob: date,
    facility_code: str = "11910105",
    pre_set_id: str = "",
    term_start: Optional[date] = None,
    term_end: Optional[date] = None,
    expected_grad_date: Optional[date] = None,
    gross_tuition: float = 0.0,
    aid_amount: float = 0.0,
    weams_confidence: float = 1.0,
) -> EMEnrollment:
    """
    Transform Decision Tree output into an EM-ready enrollment record.

    This is the bridge between Phase 1 (rule engine) and Phase 2 (EM submission).
    Every EM field is populated according to the field mapping spec.
    """

    # Map benefit chapter string to enum
    chapter_map = {
        "ch33": BenefitChapter.CH33,
        "ch35": BenefitChapter.CH35,
        "ch31": BenefitChapter.CH31,
    }
    benefit = chapter_map.get(dt_output.benefit_chapter, BenefitChapter.CH33)

    # --- Build tuition data ---
    tuition = _compute_tuition(benefit, gross_tuition, aid_amount)

    # --- Format student name (LastName, FirstName) ---
    name_parts = dt_output.student_name.split()
    if len(name_parts) >= 2:
        formatted_name = f"{name_parts[-1]}, {' '.join(name_parts[:-1])}"
    else:
        formatted_name = dt_output.student_name

    # --- Map training time ---
    training_time_labels = {
        TrainingTime.FULL_TIME: "Full-time",
        TrainingTime.THREE_QUARTER: "Three-quarter time",
        TrainingTime.HALF_TIME: "Half-time",
        TrainingTime.LESS_THAN_HALF: "Less than half-time",
        TrainingTime.QUARTER_OR_LESS: "Quarter-time or less",
    }
    training_label = training_time_labels.get(dt_output.training_time, "Unknown")

    # --- Build course detail list for audit trail ---
    course_details = []
    for cr in dt_output.course_results:
        course_details.append({
            "course_id": cr.course_id,
            "units": cr.units,
            "certifiable": cr.certifiable,
            "modality": cr.modality.value if cr.modality else None,
            "exclusion_reason": cr.exclusion_reason.value if cr.exclusion_reason else None,
            "flags": cr.flags,
        })

    # --- Compute remedial credits (certifiable remedial courses only) ---
    # Remedial credits are residential-only remedial courses that passed Step 5.
    # They're flagged in the course results.
    remedial_units = 0.0
    for cr in dt_output.course_results:
        if cr.certifiable and any("Remedial" in f for f in cr.flags):
            remedial_units += cr.units

    # --- Build the enrollment record ---
    enrollment = EMEnrollment(
        student_va_id=student_va_id,
        student_name=formatted_name,
        date_of_birth=student_dob,
        facility_code=facility_code,
        benefit_chapter=benefit,
        program_name=dt_output.weams_program,
        weams_match_confidence=weams_confidence,
        pre_set_id=pre_set_id,
        begin_date=term_start,
        end_date=term_end,
        expected_grad_date=expected_grad_date,
        resident_credits=dt_output.residential_units,
        distance_credits=dt_output.distance_units,
        remedial_credits=remedial_units,
        training_time=training_label,
        rate_of_pursuit=dt_output.rate_of_pursuit,
        mha_eligible=dt_output.mha_eligible,
        tuition=tuition,
        course_details=course_details,
    )

    # --- Generate audit trail note ---
    certifiable_ids = [
        cr.course_id for cr in dt_output.course_results if cr.certifiable
    ]
    excluded_ids = [
        cr.course_id for cr in dt_output.course_results if not cr.certifiable
    ]
    enrollment.notes = (
        f"Auto-certified via Decision Tree v0.1 on {date.today().isoformat()}. "
        f"Certifiable: {', '.join(certifiable_ids)}. "
        f"Excluded: {', '.join(excluded_ids) if excluded_ids else 'none'}. "
        f"R:{dt_output.residential_units:.0f} D:{dt_output.distance_units:.0f} "
        f"T:{dt_output.total_certifiable_units:.0f}."
    )

    # --- Run HITL escalation checks ---
    _check_hitl_triggers(enrollment, dt_output)

    return enrollment


def _compute_tuition(
    benefit: BenefitChapter,
    gross: float,
    aid: float,
) -> TuitionData:
    """
    Apply chapter-specific tuition rules.

    Ch.33: Report NET tuition (gross - tuition-designated aid)
    Non-Ch.33: Report GROSS tuition (no deductions)
    """
    tuition = TuitionData(gross_tuition=gross, aid_amount=aid)

    if benefit == BenefitChapter.CH33:
        tuition.net_tuition = max(gross - aid, 0.0)  # Can't go negative
        tuition.reported_tuition = tuition.net_tuition
        tuition.chapter_rule = "net"
    else:
        tuition.reported_tuition = gross
        tuition.chapter_rule = "gross"

    return tuition


def _check_hitl_triggers(enrollment: EMEnrollment, dt_output: DecisionTreeOutput):
    """
    Check all HITL escalation conditions. If any trigger fires,
    set status to DRAFT and record the reason.
    """
    hitl_reasons = []

    # 1. WEAMS crosswalk confidence
    if enrollment.weams_match_confidence < 0.95:
        hitl_reasons.append(HITLReason.WEAMS_LOW_CONFIDENCE)

    # 2. SCO queue items (courses needing manual review)
    if dt_output.sco_queue_items:
        hitl_reasons.append(HITLReason.SCO_QUEUE_COURSES)

    # 3. Custom remarks
    if enrollment.custom_remarks:
        hitl_reasons.append(HITLReason.CUSTOM_REMARK)

    # 4. Tuition discrepancy check (only for Ch.33 with tuition data)
    if (enrollment.tuition and
        enrollment.benefit_chapter == BenefitChapter.CH33 and
        enrollment.tuition.net_tuition < 0):
        hitl_reasons.append(HITLReason.TUITION_DISCREPANCY)

    # 5. Overall confidence score
    # Start at 1.0, deduct for each risk factor
    confidence = 1.0
    if enrollment.weams_match_confidence < 0.95:
        confidence -= 0.15
    if dt_output.sco_queue_items:
        confidence -= 0.10 * len(dt_output.sco_queue_items)
    if enrollment.remedial_credits > 0:
        confidence -= 0.05  # Minor flag — remedial needs documentation check

    enrollment.confidence_score = max(confidence, 0.0)

    if confidence < 0.90:
        hitl_reasons.append(HITLReason.LOW_CONFIDENCE)

    # Set status
    if hitl_reasons:
        enrollment.status = SubmissionStatus.DRAFT
        enrollment.hitl_reasons = hitl_reasons
    else:
        enrollment.status = SubmissionStatus.READY


# ---------------------------------------------------------------------------
# Submission Window Validation
# ---------------------------------------------------------------------------

def validate_submission_window(
    enrollment: EMEnrollment,
    submission_date: date = None,
) -> tuple[bool, str]:
    """
    Check if the enrollment can be submitted today per VA timing rules.

    Ch.33: Cannot submit more than 180 days before term start.
    Non-Ch.33: Cannot submit more than 120 days before term start.
    """
    if submission_date is None:
        submission_date = date.today()

    if enrollment.begin_date is None:
        return False, "Term start date not set."

    days_before = (enrollment.begin_date - submission_date).days

    if enrollment.benefit_chapter == BenefitChapter.CH33:
        max_advance = 180
    else:
        max_advance = 120

    if days_before > max_advance:
        return False, (
            f"Too early. {enrollment.benefit_chapter.value}: "
            f"cannot submit more than {max_advance} days before term start. "
            f"Current: {days_before} days. Earliest submission: "
            f"{(enrollment.begin_date - timedelta(days=max_advance)).isoformat()}."
        )

    return True, "Within submission window."


# ---------------------------------------------------------------------------
# Lighthouse API Client (Mock/Sandbox)
# ---------------------------------------------------------------------------

class LighthouseClient:
    """
    VA Lighthouse API client for submitting enrollments.

    Supports three modes:
      - mock:    Returns fake responses (no network calls). For testing.
      - sandbox: Hits VA sandbox endpoint (needs API key from developer.va.gov).
      - production: Hits live VA endpoint (needs production API key).

    Rate limit: 60 requests/minute. Client tracks remaining quota.
    """

    # Base URLs
    SANDBOX_URL = "https://sandbox-api.va.gov/services/benefits-intake/v1"
    PRODUCTION_URL = "https://api.va.gov/services/benefits-intake/v1"

    def __init__(self, mode: str = "mock", api_key: str = ""):
        self.mode = mode
        self.api_key = api_key
        self.base_url = (
            self.SANDBOX_URL if mode == "sandbox" else self.PRODUCTION_URL
        )

        # Rate limit tracking
        self.rate_limit = 60
        self.rate_remaining = 60
        self.rate_reset_seconds = 60

        # Submission log
        self.submissions: list[dict] = []
        self._submission_counter = 0

    def create_pre_set_enrollment(self, pre_set: PreSetEnrollment) -> dict:
        """Create a pre-set enrollment period (one per term)."""
        payload = {
            "pre_set_id": pre_set.pre_set_id,
            "school_facility_code": pre_set.facility_code,
            "term_start_date": pre_set.term_start_date.isoformat(),
            "term_end_date": pre_set.term_end_date.isoformat(),
            "vacation_periods": pre_set.vacation_periods,
            "active": pre_set.active,
        }

        return self._send("POST", "/pre-set-enrollments", payload)

    def submit_enrollment(self, enrollment: EMEnrollment) -> dict:
        """Submit a student enrollment certification to VA."""

        # Validate submission readiness
        if enrollment.status == SubmissionStatus.DRAFT:
            return {
                "success": False,
                "error": "Enrollment is in DRAFT status. SCO review required.",
                "hitl_reasons": [r.value for r in enrollment.hitl_reasons],
            }

        # Check submission window
        can_submit, window_msg = validate_submission_window(enrollment)
        if not can_submit:
            return {
                "success": False,
                "error": window_msg,
            }

        # Build API payload
        payload = self._build_enrollment_payload(enrollment)

        # Send
        response = self._send("POST", "/enrollments", payload)

        if response.get("success"):
            enrollment.status = SubmissionStatus.SUBMITTED

        return response

    def submit_amendment(self, enrollment: EMEnrollment) -> dict:
        """Submit an enrollment amendment."""
        if not enrollment.is_amendment:
            return {"success": False, "error": "Not marked as amendment."}

        payload = {
            "amendment_reason": (
                enrollment.amendment_reason.value
                if enrollment.amendment_reason else ""
            ),
            "amendment_effective_date": (
                enrollment.amendment_effective_date.isoformat()
                if enrollment.amendment_effective_date else ""
            ),
            "resident_credits": enrollment.resident_credits,
            "distance_credits": enrollment.distance_credits,
            "is_termination": enrollment.is_termination,
            "is_graduation": enrollment.is_graduation,
        }

        return self._send("POST", "/enrollments/amendment", payload)

    def get_submission_status(self, submission_id: str) -> dict:
        """Check status of a previous submission."""
        return self._send("GET", f"/uploads/{submission_id}", {})

    def _build_enrollment_payload(self, enrollment: EMEnrollment) -> dict:
        """Format EMEnrollment into the Lighthouse API request body."""
        payload = {
            "student_id": enrollment.student_va_id,
            "student_name": enrollment.student_name,
            "date_of_birth": enrollment.date_of_birth.isoformat(),
            "pre_set_id": enrollment.pre_set_id,
            "academic_institution": enrollment.facility_code,
            "benefit_type": enrollment.benefit_chapter.value,
            "program_name": enrollment.program_name,
            "begin_date": (
                enrollment.begin_date.isoformat()
                if enrollment.begin_date else None
            ),
            "end_date": (
                enrollment.end_date.isoformat()
                if enrollment.end_date else None
            ),
            "resident_credits": enrollment.resident_credits,
            "distance_credits": enrollment.distance_credits,
            "clock_hours": enrollment.clock_hours,
            "remedial_credits": enrollment.remedial_credits,
            "training_time": enrollment.training_time,
            "tuition_amount": (
                enrollment.tuition.reported_tuition
                if enrollment.tuition else 0.0
            ),
            "tuition_type": (
                enrollment.tuition.chapter_rule
                if enrollment.tuition else ""
            ),
            "remarks": enrollment.vba_remarks,
            "notes": enrollment.notes,
            "confidence_score": enrollment.confidence_score,
            "certification_statement": (
                "I certify that the information herein is true and correct "
                "to the best of my knowledge."
            ),
        }

        if enrollment.expected_grad_date:
            payload["expected_graduation_date"] = (
                enrollment.expected_grad_date.isoformat()
            )

        return payload

    def _send(self, method: str, endpoint: str, payload: dict) -> dict:
        """
        Send request to Lighthouse API.

        In mock mode: returns a fake successful response.
        In sandbox/production: would make actual HTTP request (not yet implemented).
        """

        # Rate limit check
        if self.rate_remaining <= 0:
            return {
                "success": False,
                "error": f"Rate limit exceeded. Reset in {self.rate_reset_seconds}s.",
                "retry_after": self.rate_reset_seconds,
            }

        self.rate_remaining -= 1

        if self.mode == "mock":
            return self._mock_response(method, endpoint, payload)
        else:
            # TODO: Implement actual HTTP calls when Paulina registers
            # at developer.va.gov and gets sandbox API key.
            return {
                "success": False,
                "error": (
                    f"Mode '{self.mode}' not yet implemented. "
                    f"Register at developer.va.gov for API key."
                ),
            }

    def _mock_response(self, method: str, endpoint: str, payload: dict) -> dict:
        """Generate a realistic mock response for testing."""
        self._submission_counter += 1
        submission_id = f"MOCK-{self._submission_counter:04d}"

        # Log the submission
        self.submissions.append({
            "id": submission_id,
            "method": method,
            "endpoint": endpoint,
            "payload": payload,
            "timestamp": datetime.now().isoformat(),
        })

        if "pre-set" in endpoint:
            return {
                "success": True,
                "submission_id": submission_id,
                "message": f"Pre-set enrollment created: {payload.get('pre_set_id', '')}",
                "status": "ACTIVE",
            }
        elif "amendment" in endpoint:
            return {
                "success": True,
                "submission_id": submission_id,
                "message": (
                    f"Amendment submitted: {payload.get('amendment_reason', '')}"
                ),
                "status": "AMENDMENT",
            }
        elif method == "GET":
            return {
                "success": True,
                "submission_id": submission_id,
                "status": "SUBMITTED",
                "message": "Certification received by VA. Processing.",
            }
        else:
            return {
                "success": True,
                "submission_id": submission_id,
                "message": (
                    f"Enrollment certification submitted for "
                    f"{payload.get('student_name', 'unknown')}"
                ),
                "status": "SUBMITTED",
                "rate_limit_remaining": self.rate_remaining,
            }


# ---------------------------------------------------------------------------
# Pretty-print EM enrollment
# ---------------------------------------------------------------------------

def print_em_enrollment(enrollment: EMEnrollment):
    """Print a readable summary of the EM enrollment record."""

    print("=" * 70)
    print("  EM ENROLLMENT RECORD")
    print("=" * 70)
    print(f"  Student:     {enrollment.student_name}")
    print(f"  VA ID:       {enrollment.student_va_id}")
    print(f"  DOB:         {enrollment.date_of_birth}")
    print(f"  Facility:    {enrollment.facility_code} (SDSU)")
    print(f"  Chapter:     {enrollment.benefit_chapter.value}")
    print(f"  Program:     {enrollment.program_name}")
    print(f"  WEAMS conf:  {enrollment.weams_match_confidence:.0%}")
    print("-" * 70)
    print(f"  Pre-set ID:  {enrollment.pre_set_id}")
    print(f"  Begin:       {enrollment.begin_date}")
    print(f"  End:         {enrollment.end_date}")
    if enrollment.expected_grad_date:
        print(f"  Exp. Grad:   {enrollment.expected_grad_date}")
    print("-" * 70)
    print(f"  CREDITS:")
    print(f"    Residential:  {enrollment.resident_credits:.1f}")
    print(f"    Distance:     {enrollment.distance_credits:.1f}")
    print(f"    Remedial:     {enrollment.remedial_credits:.1f}")
    print(f"    Clock Hours:  {enrollment.clock_hours:.1f}")
    total = enrollment.resident_credits + enrollment.distance_credits
    print(f"    TOTAL:        {total:.1f}")
    print(f"  Training:    {enrollment.training_time} (RoP: {enrollment.rate_of_pursuit:.0%})")
    print(f"  MHA:         {'Eligible' if enrollment.mha_eligible else 'Not eligible'}")
    print("-" * 70)

    if enrollment.tuition:
        t = enrollment.tuition
        print(f"  TUITION ({t.chapter_rule.upper()}):")
        print(f"    Gross:     ${t.gross_tuition:,.2f}")
        if t.chapter_rule == "net":
            print(f"    Aid:       -${t.aid_amount:,.2f}")
            print(f"    Net:       ${t.net_tuition:,.2f}")
        print(f"    Reported:  ${t.reported_tuition:,.2f}")
        print("-" * 70)

    print(f"  STATUS:      {enrollment.status.value.upper()}")
    print(f"  Confidence:  {enrollment.confidence_score:.0%}")

    if enrollment.hitl_reasons:
        print(f"  HITL FLAGS ({len(enrollment.hitl_reasons)}):")
        for reason in enrollment.hitl_reasons:
            print(f"    - {reason.value}")

    if enrollment.notes:
        print(f"\n  NOTES:")
        print(f"    {enrollment.notes}")

    print("=" * 70)


# ---------------------------------------------------------------------------
# JAMES ROSTER — Full Pipeline Test
# ---------------------------------------------------------------------------

def james_roster_pipeline_test():
    """
    End-to-end test: Decision Tree → EM Fields → API Payload.

    Uses James Roster (Daniel Bahena), B.A. Journalism, Ch.33, Fall 2024.
    Expected: R:6, D:6, T:12, ENS 331 excluded, status=READY.
    """

    print("\n" + "=" * 70)
    print("  PHASE 2 PIPELINE TEST: JAMES ROSTER END-TO-END")
    print("=" * 70)

    # -------------------------------------------------------------------
    # Step A: Run Decision Tree (Phase 1)
    # -------------------------------------------------------------------
    print("\n>>> STEP A: Decision Tree\n")

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
    print_results(dt_output)

    # -------------------------------------------------------------------
    # Step B: Format for EM (Phase 2)
    # -------------------------------------------------------------------
    print("\n>>> STEP B: EM Field Formatting\n")

    enrollment = format_for_em(
        dt_output=dt_output,
        student_va_id="***-**-1234",          # Masked SSN
        student_dob=date(1998, 3, 15),
        facility_code="11910105",
        pre_set_id="Fall-2024",
        term_start=date(2024, 8, 21),
        term_end=date(2024, 12, 11),
        gross_tuition=3898.00,                 # SDSU in-state ~$8,290/yr; per-term from PS TUITION_CALC_TBL
        aid_amount=1200.00,                    # Example aid — real value from SSR_VB_TF_SETUP
        weams_confidence=0.98,                 # High confidence match
    )

    print_em_enrollment(enrollment)

    # -------------------------------------------------------------------
    # Step C: Submit via Lighthouse API (Mock)
    # -------------------------------------------------------------------
    print("\n>>> STEP C: Lighthouse API Submission (Mock)\n")

    client = LighthouseClient(mode="mock")

    # First create the pre-set enrollment
    pre_set = PreSetEnrollment(
        pre_set_id="Fall-2024",
        facility_code="11910105",
        term_start_date=date(2024, 8, 21),
        term_end_date=date(2024, 12, 11),
    )
    pre_set_response = client.create_pre_set_enrollment(pre_set)
    print(f"  Pre-set: {pre_set_response['message']}")
    print(f"    ID: {pre_set_response['submission_id']}")

    # Then submit the enrollment
    enroll_response = client.submit_enrollment(enrollment)
    print(f"\n  Enrollment: {enroll_response['message']}")
    print(f"    ID: {enroll_response['submission_id']}")
    print(f"    Status: {enroll_response['status']}")
    print(f"    Rate limit remaining: {enroll_response.get('rate_limit_remaining', 'N/A')}")

    # -------------------------------------------------------------------
    # Step D: Show the full API payload
    # -------------------------------------------------------------------
    print("\n>>> STEP D: Full API Payload\n")

    payload = client.submissions[-1]["payload"]
    print(json.dumps(payload, indent=2, default=str))

    # -------------------------------------------------------------------
    # REGRESSION CHECKS
    # -------------------------------------------------------------------
    print("\n  REGRESSION CHECK:")

    checks_passed = 0
    checks_total = 0

    def check(desc, actual, expected):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            checks_passed += 1
        print(f"    [{status}] {desc}: expected={expected}, got={actual}")

    # EM field checks
    check("Status (post-submit)", enrollment.status, SubmissionStatus.SUBMITTED)
    check("Resident credits", enrollment.resident_credits, 6.0)
    check("Distance credits", enrollment.distance_credits, 6.0)
    check("Remedial credits", enrollment.remedial_credits, 0.0)
    check("Training time", enrollment.training_time, "Full-time")
    check("MHA eligible", enrollment.mha_eligible, True)
    check("Confidence", enrollment.confidence_score, 1.0)
    check("HITL reasons", len(enrollment.hitl_reasons), 0)

    # Tuition checks (Ch.33 = net)
    check("Tuition rule", enrollment.tuition.chapter_rule, "net")
    check("Gross tuition", enrollment.tuition.gross_tuition, 3898.00)
    check("Aid amount", enrollment.tuition.aid_amount, 1200.00)
    check("Net tuition", enrollment.tuition.net_tuition, 2698.00)
    check("Reported tuition", enrollment.tuition.reported_tuition, 2698.00)

    # API response checks
    check("Pre-set success", pre_set_response["success"], True)
    check("Enrollment success", enroll_response["success"], True)
    check("Enrollment status", enroll_response["status"], "SUBMITTED")

    # Payload spot checks
    check("Payload student_id", payload["student_id"], "***-**-1234")
    check("Payload facility", payload["academic_institution"], "11910105")
    check("Payload R credits", payload["resident_credits"], 6.0)
    check("Payload D credits", payload["distance_credits"], 6.0)
    check("Payload tuition", payload["tuition_amount"], 2698.00)
    check("Payload tuition type", payload["tuition_type"], "net")

    print(f"\n    {checks_passed}/{checks_total} checks passed.")

    if checks_passed == checks_total:
        print("\n    *** JAMES ROSTER PIPELINE: ALL CHECKS PASSED ***")
    else:
        print(f"\n    *** JAMES ROSTER PIPELINE: {checks_total - checks_passed} FAILURES ***")

    return enrollment, client


# ---------------------------------------------------------------------------
# HITL Escalation Test
# ---------------------------------------------------------------------------

def hitl_escalation_test():
    """
    Test that the HITL system correctly flags risky enrollments as DRAFT.

    Uses a synthetic student with low WEAMS confidence + SCO queue items.
    Expected: status=DRAFT, multiple HITL reasons.
    """
    print("\n" + "=" * 70)
    print("  HITL ESCALATION TEST")
    print("=" * 70)

    # Build a Decision Tree output with SCO queue items
    student = StudentInput(
        name="Test Student C",
        student_id="HITL-001",
        program="B.S. Computer Science",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Spring 2025",
        courses=[
            CourseSchedule(
                course_id="CS 101", title="Intro to CS", units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True, dars_rationale="major",
                has_in_person_session=True, all_online=False,
            ),
            # This one will route to SCO queue
            CourseSchedule(
                course_id="HIST 200", title="World History", units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=False,
                has_sco_exception=True, sco_exception_type="advisor approval",
                has_in_person_session=True, all_online=False,
            ),
        ],
    )

    dt_output = run_decision_tree(student)

    # Format with LOW WEAMS confidence to trigger HITL
    enrollment = format_for_em(
        dt_output=dt_output,
        student_va_id="***-**-5678",
        student_dob=date(2000, 6, 20),
        pre_set_id="Spring-2025",
        term_start=date(2025, 1, 21),
        term_end=date(2025, 5, 15),
        gross_tuition=3898.00,
        aid_amount=0.0,
        weams_confidence=0.82,  # Below 95% threshold
    )

    print_em_enrollment(enrollment)

    # Try to submit — should be blocked
    client = LighthouseClient(mode="mock")
    response = client.submit_enrollment(enrollment)

    print(f"\n  Submission attempt: {response.get('error', response.get('message', ''))}")

    # Regression checks
    print("\n  REGRESSION CHECK:")

    checks_passed = 0
    checks_total = 0

    def check(desc, actual, expected):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            checks_passed += 1
        print(f"    [{status}] {desc}: expected={expected}, got={actual}")

    check("Status", enrollment.status, SubmissionStatus.DRAFT)
    check("Submission blocked", response["success"], False)
    check("Has HITL reasons", len(enrollment.hitl_reasons) >= 2, True)
    check("WEAMS flag present",
          HITLReason.WEAMS_LOW_CONFIDENCE in enrollment.hitl_reasons, True)
    check("SCO queue flag present",
          HITLReason.SCO_QUEUE_COURSES in enrollment.hitl_reasons, True)
    check("Confidence below 90%", enrollment.confidence_score < 0.90, True)

    print(f"\n    {checks_passed}/{checks_total} checks passed.")

    if checks_passed == checks_total:
        print("\n    *** HITL ESCALATION TEST: ALL CHECKS PASSED ***")
    else:
        print(f"\n    *** HITL ESCALATION TEST: {checks_total - checks_passed} FAILURES ***")


# ---------------------------------------------------------------------------
# Ch.35 Gross Tuition Test
# ---------------------------------------------------------------------------

def ch35_tuition_test():
    """
    Verify that Ch.35 uses GROSS tuition (no aid deduction).
    """
    print("\n" + "=" * 70)
    print("  CH.35 GROSS TUITION TEST")
    print("=" * 70)

    student = StudentInput(
        name="Test Student D",
        student_id="CH35-001",
        program="B.A. Journalism",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch35",
        term="Fall 2025",
        courses=[
            CourseSchedule(
                course_id="JMS 200", title="News Writing", units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True, dars_rationale="major",
                has_in_person_session=True, all_online=False,
            ),
        ],
    )

    dt_output = run_decision_tree(student)

    enrollment = format_for_em(
        dt_output=dt_output,
        student_va_id="***-**-9999",
        student_dob=date(2001, 11, 1),
        pre_set_id="Fall-2025",
        term_start=date(2025, 8, 20),
        term_end=date(2025, 12, 10),
        gross_tuition=3898.00,
        aid_amount=1500.00,  # Aid exists but should NOT be deducted
    )

    print(f"\n  Chapter:    {enrollment.benefit_chapter.value}")
    print(f"  Gross:      ${enrollment.tuition.gross_tuition:,.2f}")
    print(f"  Aid:        ${enrollment.tuition.aid_amount:,.2f}")
    print(f"  Reported:   ${enrollment.tuition.reported_tuition:,.2f}")
    print(f"  Rule:       {enrollment.tuition.chapter_rule}")

    # Regression checks
    print("\n  REGRESSION CHECK:")

    checks_passed = 0
    checks_total = 0

    def check(desc, actual, expected):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            checks_passed += 1
        print(f"    [{status}] {desc}: expected={expected}, got={actual}")

    check("Tuition rule", enrollment.tuition.chapter_rule, "gross")
    check("Reported = gross (not net)",
          enrollment.tuition.reported_tuition, 3898.00)
    check("MHA not eligible (ch35)", enrollment.mha_eligible, False)

    print(f"\n    {checks_passed}/{checks_total} checks passed.")

    if checks_passed == checks_total:
        print("\n    *** CH.35 TUITION TEST: ALL CHECKS PASSED ***")
    else:
        print(f"\n    *** CH.35 TUITION TEST: {checks_total - checks_passed} FAILURES ***")


# ---------------------------------------------------------------------------
# RUN ALL PHASE 2 TESTS
# ---------------------------------------------------------------------------

def run_all_phase2_tests():
    """Run the full Phase 2 regression suite."""
    print("\n" + "=" * 70)
    print("  PHASE 2 — EM INTEGRATION — FULL TEST SUITE")
    print("=" * 70)

    james_roster_pipeline_test()
    hitl_escalation_test()
    ch35_tuition_test()

    print("\n" + "=" * 70)
    print("  PHASE 2 TEST SUITE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_all_phase2_tests()
