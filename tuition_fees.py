"""
Tuition & Fees Certification Module — VA Dual Certification Model
==================================================================
Handles T&F certification separately from enrollment certification per SCO Handbook.

The VA requires TWO separate certifications:
1. Enrollment certification — student's courses, units, training time, modality (enrollment_monitor.py)
2. Tuition & Fees certification — reported SEPARATELY after census (this module)

T&F certification is critical for Ch. 33 (Post-9/11) students — VA pays tuition & fees
directly to the school. Other chapters have different payment models.

T&F Timing at SDSU:
  - Census date: Sept 21, 2026
  - T&F can be reported: Sept 22+ (day after census)
  - Typical delay: ~1 week (waiting on bursar's office report from Mamie Miller)
  - Worst case: up to a month if Mamie is out or on leave
  - Bottleneck is human, not system

Authority: SCO Handbook Rev 7.4; 38 CFR Part 21
Validated by: Paulina, SCO at SDSU
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional

from enrollment_monitor import SDSU_FALL_2026


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BenefitChapter(Enum):
    """VA benefit chapters."""
    CH33 = "ch33"  # Post-9/11 GI Bill — VA pays tuition/fees directly to school
    CH35 = "ch35"  # Dependents' Educational Assistance (DEA) — monthly stipend
    CH31 = "ch31"  # Veterans Readiness & Employment (VR&E) — varies
    OTHER = "other"


class TFStatus(Enum):
    """Tuition & Fees certification status."""
    PENDING_BURSAR_REPORT = "pending_bursar_report"  # Waiting on bursar's office
    RECEIVED = "received"  # Bursar report received, not yet certified
    CERTIFIED_TO_VA = "certified_to_va"  # Submitted to VA
    AMENDED = "amended"  # Amendment submitted


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class TFAmendment:
    """
    A tuition & fees amendment record.

    Tracks the difference between original and revised amounts,
    with reason and timestamp for audit trail.
    """
    original_tuition: float
    original_fees: float
    revised_tuition: float
    revised_fees: float
    reason: str
    timestamp: datetime

    @property
    def tuition_delta(self) -> float:
        """Delta in tuition amount."""
        return self.revised_tuition - self.original_tuition

    @property
    def fees_delta(self) -> float:
        """Delta in fees amount."""
        return self.revised_fees - self.original_fees

    @property
    def total_delta(self) -> float:
        """Total delta in tuition + fees."""
        return self.tuition_delta + self.fees_delta


@dataclass
class TuitionFeeRecord:
    """
    A single T&F record for a student-term.

    Captures:
      - Student and term identification
      - Benefit chapter (ch33, ch35, ch31, other)
      - Tuition and fees amounts
      - Reporting and certification dates
      - Current status in the T&F workflow
      - Facility code (for multi-institution support)
    """
    student_id: str
    term: str  # e.g., "Fall 2026"
    chapter: BenefitChapter
    tuition_amount: float
    fees_amount: float
    facility_code: str

    # Reporting data (from bursar)
    reported_date: Optional[datetime] = None

    # Status tracking
    status: TFStatus = TFStatus.PENDING_BURSAR_REPORT

    # Certification data
    certified_date: Optional[datetime] = None

    # Amendment history
    amendment_history: list = field(default_factory=list)  # list of TFAmendment

    @property
    def total(self) -> float:
        """Total tuition + fees."""
        return self.tuition_amount + self.fees_amount

    @property
    def is_chapter_33(self) -> bool:
        """True if this is a Ch. 33 student."""
        return self.chapter == BenefitChapter.CH33

    @property
    def last_amendment(self) -> Optional[TFAmendment]:
        """Get the most recent amendment, if any."""
        return self.amendment_history[-1] if self.amendment_history else None


@dataclass
class TFCertification:
    """
    A T&F certification wrapper with metadata.

    Contains:
      - The underlying T&F record
      - Certification metadata (dates, notes)
      - Amendment history for audit trail
    """
    record: TuitionFeeRecord
    cert_date: Optional[datetime] = None
    notes: str = ""

    @property
    def student_id(self) -> str:
        return self.record.student_id

    @property
    def term(self) -> str:
        return self.record.term

    @property
    def status(self) -> TFStatus:
        return self.record.status


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------

def create_tf_record(
    student_id: str,
    term: str,
    chapter: BenefitChapter,
    tuition: float,
    fees: float,
    facility_code: str,
) -> TuitionFeeRecord:
    """
    Create a new T&F record for a student-term.

    Initial status is PENDING_BURSAR_REPORT (waiting on bursar's office).

    Args:
        student_id: Student's ID
        term: Term (e.g., "Fall 2026")
        chapter: Benefit chapter (ch33, ch35, etc.)
        tuition: Initial tuition amount (may be placeholder)
        fees: Initial fees amount (may be placeholder)
        facility_code: Facility code (e.g., "11910105" for SDSU)

    Returns:
        A new TuitionFeeRecord with status PENDING_BURSAR_REPORT
    """
    return TuitionFeeRecord(
        student_id=student_id,
        term=term,
        chapter=chapter,
        tuition_amount=tuition,
        fees_amount=fees,
        facility_code=facility_code,
        reported_date=None,
        status=TFStatus.PENDING_BURSAR_REPORT,
        certified_date=None,
        amendment_history=[],
    )


def report_tf_from_bursar(
    record: TuitionFeeRecord,
    tuition: float,
    fees: float,
    reported_date: datetime,
) -> TuitionFeeRecord:
    """
    Update a T&F record with actual amounts from the bursar's office.

    This is called when Mamie Miller (bursar) provides the official tuition & fees report.

    Args:
        record: The T&F record to update
        tuition: Actual tuition amount from bursar
        fees: Actual fees amount from bursar
        reported_date: When the bursar report was received

    Returns:
        Updated record with status RECEIVED

    Raises:
        ValueError: If record is already certified
    """
    if record.status == TFStatus.CERTIFIED_TO_VA or record.status == TFStatus.AMENDED:
        raise ValueError(
            f"Cannot update T&F record that is already certified "
            f"(student {record.student_id}, term {record.term}, status {record.status.value})"
        )

    record.tuition_amount = tuition
    record.fees_amount = fees
    record.reported_date = reported_date
    record.status = TFStatus.RECEIVED

    return record


def certify_tf_to_va(
    record: TuitionFeeRecord,
    academic_calendar: Optional[dict] = None,
    override_date_check: bool = False,
) -> TuitionFeeRecord:
    """
    Mark a T&F record as certified to VA.

    Validates that:
      1. The record status is RECEIVED (bursar report has been received)
      2. The current date is AFTER the census date (VA won't accept pre-census T&F)

    Args:
        record: The T&F record to certify
        academic_calendar: Academic calendar dict with census_date key
                          (defaults to SDSU_FALL_2026)
        override_date_check: If True, skip the census date validation (testing only)

    Returns:
        Updated record with status CERTIFIED_TO_VA

    Raises:
        ValueError: If record is not in RECEIVED status or if before census date
    """
    if record.status != TFStatus.RECEIVED:
        raise ValueError(
            f"Cannot certify T&F record not in RECEIVED status "
            f"(student {record.student_id}, current status: {record.status.value})"
        )

    if not override_date_check:
        cal = academic_calendar or SDSU_FALL_2026
        census_date = cal["census_date"]
        today = date.today()

        if today < census_date:
            raise ValueError(
                f"Cannot certify T&F before census date "
                f"(census: {census_date}, today: {today})"
            )

    record.status = TFStatus.CERTIFIED_TO_VA
    record.certified_date = datetime.now()

    return record


def amend_tf(
    record: TuitionFeeRecord,
    new_tuition: float,
    new_fees: float,
    reason: str,
) -> TuitionFeeRecord:
    """
    Create a T&F amendment (e.g., tuition changed after initial report).

    Creates an amendment record tracking the delta between original and revised amounts.

    Args:
        record: The T&F record to amend
        new_tuition: Revised tuition amount
        new_fees: Revised fees amount
        reason: Reason for amendment (e.g., "Course drop after census")

    Returns:
        Updated record with amendment added and status AMENDED

    Raises:
        ValueError: If record has not been certified yet
    """
    if record.status == TFStatus.PENDING_BURSAR_REPORT or record.status == TFStatus.RECEIVED:
        raise ValueError(
            f"Cannot amend T&F record that is not certified "
            f"(student {record.student_id}, current status: {record.status.value})"
        )

    amendment = TFAmendment(
        original_tuition=record.tuition_amount,
        original_fees=record.fees_amount,
        revised_tuition=new_tuition,
        revised_fees=new_fees,
        reason=reason,
        timestamp=datetime.now(),
    )

    record.amendment_history.append(amendment)
    record.tuition_amount = new_tuition
    record.fees_amount = new_fees
    record.status = TFStatus.AMENDED

    return record


def get_tf_status(
    student_id: str,
    term: str,
    records: list[TuitionFeeRecord],
) -> Optional[TFCertification]:
    """
    Retrieve the current T&F certification status for a student-term.

    Args:
        student_id: Student's ID
        term: Term (e.g., "Fall 2026")
        records: List of all T&F records to search

    Returns:
        A TFCertification object if found, None otherwise
    """
    for record in records:
        if record.student_id == student_id and record.term == term:
            return TFCertification(record=record)

    return None


def get_pending_tf_reports(
    term: str,
    facility_code: str,
    all_enrollments: list,  # EnrollmentSnapshot objects from enrollment_monitor
    tf_records: list[TuitionFeeRecord],
) -> list[dict]:
    """
    Get all Ch. 33 students who have enrollment certified but T&F still pending.

    This is what the SCO dashboard would show as the "pending T&F queue" —
    students whose enrollment has been certified to VA but whose tuition & fees
    have not yet been reported (still waiting on bursar).

    Args:
        term: Term (e.g., "Fall 2026")
        facility_code: Facility code (e.g., "11910105" for SDSU)
        all_enrollments: List of EnrollmentSnapshot objects (from enrollment_monitor)
        tf_records: List of all TuitionFeeRecord objects

    Returns:
        List of dicts with keys:
          - student_id
          - chapter
          - enrollment_status (from enrollment_monitor)
          - tf_status (from tuition_fees module)
          - tuition (current amount)
          - fees (current amount)
          - total
          - days_since_census
    """

    cal = SDSU_FALL_2026
    census_date = cal["census_date"]

    pending = []

    # Get all Ch. 33 students with certified enrollment for this term
    for enrollment in all_enrollments:
        if enrollment.term != term or enrollment.facility_code != facility_code:
            continue

        if enrollment.last_certified is None:
            continue  # Enrollment not certified yet

        # Find corresponding T&F record
        tf_record = None
        for rec in tf_records:
            if rec.student_id == enrollment.student_id and rec.term == term:
                tf_record = rec
                break

        # If no T&F record exists, create placeholder (pending_bursar_report)
        if tf_record is None:
            tf_record = TuitionFeeRecord(
                student_id=enrollment.student_id,
                term=term,
                chapter=BenefitChapter.CH33,  # Assume Ch. 33 if queried
                tuition_amount=0.0,
                fees_amount=0.0,
                facility_code=facility_code,
                status=TFStatus.PENDING_BURSAR_REPORT,
            )

        # Only include Ch. 33 students
        if tf_record.chapter != BenefitChapter.CH33:
            continue

        # Only include those NOT yet certified to VA
        if tf_record.status in [TFStatus.CERTIFIED_TO_VA, TFStatus.AMENDED]:
            continue

        # Calculate days since census
        today = date.today()
        days_since = (today - census_date).days

        pending.append({
            "student_id": enrollment.student_id,
            "chapter": tf_record.chapter.value,
            "enrollment_status": "certified" if enrollment.last_certified else "pending",
            "tf_status": tf_record.status.value,
            "tuition": tf_record.tuition_amount,
            "fees": tf_record.fees_amount,
            "total": tf_record.total,
            "days_since_census": days_since,
        })

    # Sort by days_since_census (longest waiting first)
    pending.sort(key=lambda x: x["days_since_census"], reverse=True)

    return pending


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """
    Run test suite for T&F module.

    Test 1: Create T&F record, report from bursar, certify to VA
    Test 2: T&F amendment after certification
    Test 3: get_pending_tf_reports returns correct students
    Test 4: Validate cannot certify before census date
    """

    def check(description, actual, expected):
        """Helper function for assertions."""
        status = "PASS" if actual == expected else "FAIL"
        if status == "FAIL":
            print(f"    [{status}] {description}")
            print(f"      Expected: {expected}")
            print(f"      Got:      {actual}")
        else:
            print(f"    [{status}] {description}")
        return status == "PASS"

    total_checks = 0
    passed_checks = 0

    # =======================================================================
    # TEST 1: Create T&F record, report from bursar, certify to VA
    # =======================================================================
    print("\n" + "=" * 70)
    print("  TEST 1: CREATE → REPORT → CERTIFY")
    print("  (Ch. 33 student, SDSU Fall 2026)")
    print("=" * 70)

    # Create a T&F record
    record = create_tf_record(
        student_id="STU-001",
        term="Fall 2026",
        chapter=BenefitChapter.CH33,
        tuition=15000.0,
        fees=800.0,
        facility_code="11910105",
    )

    # Check initial state
    total_checks += 1
    if check("Initial status is PENDING_BURSAR_REPORT",
             record.status, TFStatus.PENDING_BURSAR_REPORT):
        passed_checks += 1

    total_checks += 1
    if check("Initial reported_date is None", record.reported_date, None):
        passed_checks += 1

    total_checks += 1
    if check("Total = tuition + fees", record.total, 15800.0):
        passed_checks += 1

    # Report from bursar (day after census)
    census_date = SDSU_FALL_2026["census_date"]
    bursar_report_date = datetime(
        census_date.year, census_date.month, census_date.day + 1, 10, 0, 0
    )

    report_tf_from_bursar(
        record=record,
        tuition=15200.0,  # Slightly different from placeholder
        fees=820.0,
        reported_date=bursar_report_date,
    )

    total_checks += 1
    if check("Status after bursar report is RECEIVED",
             record.status, TFStatus.RECEIVED):
        passed_checks += 1

    total_checks += 1
    if check("Tuition updated from bursar", record.tuition_amount, 15200.0):
        passed_checks += 1

    total_checks += 1
    if check("Fees updated from bursar", record.fees_amount, 820.0):
        passed_checks += 1

    # Certify to VA (must be after census, use override for testing)
    certify_tf_to_va(record, academic_calendar=SDSU_FALL_2026, override_date_check=True)

    total_checks += 1
    if check("Status after certification is CERTIFIED_TO_VA",
             record.status, TFStatus.CERTIFIED_TO_VA):
        passed_checks += 1

    total_checks += 1
    if check("certified_date is set", record.certified_date is not None, True):
        passed_checks += 1

    # =======================================================================
    # TEST 2: T&F Amendment
    # =======================================================================
    print("\n" + "=" * 70)
    print("  TEST 2: T&F AMENDMENT (TUITION CHANGES)")
    print("  (Scenario: student drops a course, refund issued)")
    print("=" * 70)

    # Start with a certified record
    original_record = create_tf_record(
        student_id="STU-002",
        term="Fall 2026",
        chapter=BenefitChapter.CH33,
        tuition=16000.0,
        fees=900.0,
        facility_code="11910105",
    )

    report_tf_from_bursar(
        record=original_record,
        tuition=16000.0,
        fees=900.0,
        reported_date=bursar_report_date,
    )

    certify_tf_to_va(original_record, academic_calendar=SDSU_FALL_2026, override_date_check=True)

    # Now amend (course drop, refund of $3000)
    amend_tf(
        record=original_record,
        new_tuition=13000.0,  # 16000 - 3000 refund
        new_fees=900.0,
        reason="Course drop after census — refund issued",
    )

    total_checks += 1
    if check("Status after amendment is AMENDED",
             original_record.status, TFStatus.AMENDED):
        passed_checks += 1

    total_checks += 1
    if check("Amendment in history", len(original_record.amendment_history), 1):
        passed_checks += 1

    if original_record.amendment_history:
        amendment = original_record.amendment_history[0]

        total_checks += 1
        if check("Amendment original tuition", amendment.original_tuition, 16000.0):
            passed_checks += 1

        total_checks += 1
        if check("Amendment revised tuition", amendment.revised_tuition, 13000.0):
            passed_checks += 1

        total_checks += 1
        if check("Amendment tuition_delta", amendment.tuition_delta, -3000.0):
            passed_checks += 1

        total_checks += 1
        if check("Amendment fees_delta", amendment.fees_delta, 0.0):
            passed_checks += 1

        total_checks += 1
        if check("Amendment total_delta", amendment.total_delta, -3000.0):
            passed_checks += 1

    total_checks += 1
    if check("Current tuition after amendment", original_record.tuition_amount, 13000.0):
        passed_checks += 1

    # =======================================================================
    # TEST 3: get_pending_tf_reports
    # =======================================================================
    print("\n" + "=" * 70)
    print("  TEST 3: GET PENDING T&F REPORTS")
    print("  (SCO dashboard query: Ch. 33 students with enrolled certs)")
    print("=" * 70)

    # Create mock enrollments (from enrollment_monitor)
    from enrollment_monitor import EnrollmentSnapshot, EnrolledCourse, CourseEnrollmentStatus
    from decision_tree import Modality, DecisionTreeOutput, TrainingTime

    # Build mock DecisionTreeOutput for students
    mock_cert = DecisionTreeOutput(
        student_name="Test Student",
        student_id="STU-003",
        program="B.A. Engineering",
        term="Fall 2026",
        benefit_chapter="ch33",
        total_enrolled_units=12.0,
        total_certifiable_units=12.0,
        residential_units=9.0,
        distance_units=3.0,
        training_time=TrainingTime.FULL_TIME,
        rate_of_pursuit=1.0,
    )

    # Ch. 33 student with enrollment certified, T&F pending
    enrollment_stu3 = EnrollmentSnapshot(
        student_id="STU-003",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 9, 25, 10, 0, 0),
        courses=[
            EnrolledCourse("MATH 150", "Calculus I", 4.0, Modality.RESIDENTIAL, CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse("PHYS 195", "Physics I", 4.0, Modality.RESIDENTIAL, CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse("CS 101", "Intro to CS", 4.0, Modality.DISTANCE, CourseEnrollmentStatus.ENROLLED),
        ],
        last_certified=mock_cert,
    )

    # Ch. 33 student with enrollment certified, T&F already certified
    enrollment_stu4 = EnrollmentSnapshot(
        student_id="STU-004",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 9, 25, 10, 0, 0),
        courses=[],
        last_certified=mock_cert,
    )

    # Ch. 35 student (not Ch. 33, should be excluded)
    enrollment_stu5 = EnrollmentSnapshot(
        student_id="STU-005",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 9, 25, 10, 0, 0),
        courses=[],
        last_certified=mock_cert,
    )

    # Create T&F records
    tf_stu3 = create_tf_record("STU-003", "Fall 2026", BenefitChapter.CH33, 15000.0, 800.0, "11910105")

    tf_stu4 = create_tf_record("STU-004", "Fall 2026", BenefitChapter.CH33, 16000.0, 900.0, "11910105")
    report_tf_from_bursar(tf_stu4, 16000.0, 900.0, bursar_report_date)
    certify_tf_to_va(tf_stu4, academic_calendar=SDSU_FALL_2026, override_date_check=True)

    tf_stu5 = create_tf_record("STU-005", "Fall 2026", BenefitChapter.CH35, 10000.0, 500.0, "11910105")

    all_enrollments = [enrollment_stu3, enrollment_stu4, enrollment_stu5]
    all_tf_records = [tf_stu3, tf_stu4, tf_stu5]

    pending = get_pending_tf_reports(
        term="Fall 2026",
        facility_code="11910105",
        all_enrollments=all_enrollments,
        tf_records=all_tf_records,
    )

    total_checks += 1
    if check("Pending reports count (should only include STU-003)",
             len(pending), 1):
        passed_checks += 1

    if pending:
        stu3_pending = pending[0]

        total_checks += 1
        if check("Pending student ID is STU-003",
                 stu3_pending["student_id"], "STU-003"):
            passed_checks += 1

        total_checks += 1
        if check("Pending status is pending_bursar_report",
                 stu3_pending["tf_status"], "pending_bursar_report"):
            passed_checks += 1

        total_checks += 1
        if check("Pending chapter is ch33",
                 stu3_pending["chapter"], "ch33"):
            passed_checks += 1

    # =======================================================================
    # TEST 4: Cannot certify before census date
    # =======================================================================
    print("\n" + "=" * 70)
    print("  TEST 4: VALIDATE CANNOT CERTIFY BEFORE CENSUS")
    print("  (Business rule: T&F cannot be certified pre-census)")
    print("=" * 70)

    # Create a record and report it, but try to certify before census
    pre_census_record = create_tf_record(
        student_id="STU-006",
        term="Fall 2026",
        chapter=BenefitChapter.CH33,
        tuition=15000.0,
        fees=800.0,
        facility_code="11910105",
    )

    pre_census_date = datetime(
        census_date.year, census_date.month, census_date.day - 5, 10, 0, 0
    )

    report_tf_from_bursar(
        record=pre_census_record,
        tuition=15000.0,
        fees=800.0,
        reported_date=pre_census_date,
    )

    # Try to certify (should raise ValueError if before census)
    # We create a mock calendar with today before census
    mock_calendar = {
        "instruction_begins": SDSU_FALL_2026["instruction_begins"],
        "add_drop_deadline": SDSU_FALL_2026["add_drop_deadline"],
        "census_date": date(2026, 12, 1),  # Future date
        "withdrawal_deadline": SDSU_FALL_2026["withdrawal_deadline"],
        "last_day_instruction": SDSU_FALL_2026["last_day_instruction"],
        "finals_begin": SDSU_FALL_2026["finals_begin"],
        "finals_end": SDSU_FALL_2026["finals_end"],
        "semester_end": SDSU_FALL_2026["semester_end"],
    }

    try:
        certify_tf_to_va(pre_census_record, academic_calendar=mock_calendar)
        total_checks += 1
        passed_checks += 0  # Should have raised an error
        print("    [FAIL] Should have raised ValueError for pre-census certification")
    except ValueError as e:
        total_checks += 1
        if "census date" in str(e).lower():
            passed_checks += 1
            print(f"    [PASS] Correctly rejected pre-census certification: {e}")
        else:
            print(f"    [FAIL] Wrong error message: {e}")

    # =======================================================================
    # Summary
    # =======================================================================
    print("\n" + "=" * 70)
    print(f"  TEST SUMMARY: {passed_checks}/{total_checks} checks passed")
    print("=" * 70)

    if passed_checks == total_checks:
        print("\n  *** ALL TESTS PASSED ***\n")
        exit(0)
    else:
        print(f"\n  *** {total_checks - passed_checks} TEST(S) FAILED ***\n")
        exit(1)
