"""
VA Enrollment Change Monitoring & Amendment Engine — Phase 3
=============================================================
Detects enrollment changes AFTER initial certification and generates
amendments for re-certification to VA Enrollment Manager.

Architecture:
  1. EnrollmentSnapshot — Captures a student's enrollment state at a point in time
  2. ChangeType + EnrollmentChange — Detects what changed between snapshots
  3. AmendmentReason + AmendmentRecord — Maps changes to VA amendment types
  4. detect_changes() — Compare snapshots and identify all deltas
  5. generate_amendment() — Re-run Decision Tree on modified enrollment, emit AmendmentRecord
  6. process_enrollment_updates() — Batch processor for dashboard integration

Authority: SCO Handbook Rev 7.4; 38 CFR Part 21; EM Amendment Rules
Validated by: Paulina, SCO at SDSU

Phase 3 flow (from dashboard):
  1. Monitor pulls old & new enrollment snapshots from PeopleSoft (STDNT_ENRL + LAST_UPD_DT_STMP)
  2. detect_changes() identifies deltas (course drops, units changes, etc.)
  3. generate_amendment() re-certifies the modified schedule → AmendmentRecord
  4. Dashboard presents AmendmentRecords to SCO for review
  5. SCO approves or modifies → submitted via em_integration.submit_amendment()
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional, Tuple

from decision_tree import (
    StudentInput,
    CourseSchedule,
    DecisionTreeOutput,
    run_decision_tree,
    TrainingTime,
    Modality,
)


# ---------------------------------------------------------------------------
# SDSU Fall 2026 Academic Calendar (from registrar.sdsu.edu)
# Source: https://registrar.sdsu.edu/calendars/academic/fall-2026
# ---------------------------------------------------------------------------

SDSU_FALL_2026 = {
    "instruction_begins":   date(2026, 8, 24),  # First Day of Classes
    "add_drop_deadline":    date(2026, 9, 4),   # Last day to add/drop (11:59 PM)
    "census_date":          date(2026, 9, 21),  # Census
    "withdrawal_deadline":  date(2026, 11, 1),  # Last day to withdraw (prorated refund)
    "last_day_instruction": date(2026, 12, 11), # Last day of classes
    "finals_begin":         date(2026, 12, 12), # Final exams begin
    "finals_end":           date(2026, 12, 18), # Final exams end
    "semester_end":         date(2026, 12, 31), # Last day of fall semester
}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ChangeType(Enum):
    """Types of enrollment changes detected between snapshots."""
    COURSE_ADDED = "course_added"
    COURSE_DROPPED = "course_dropped"
    COURSE_WITHDRAWN = "course_withdrawn"  # Enrolled → Withdrawn status
    UNITS_CHANGED = "units_changed"
    PROGRAM_CHANGED = "program_changed"
    GRADUATION = "graduation"


class CourseEnrollmentStatus(Enum):
    """Status of a course in a student's enrollment."""
    ENROLLED = "enrolled"
    DROPPED = "dropped"
    WITHDRAWN = "withdrawn"  # After add/drop period


class AmendmentReason(Enum):
    """
    VA Enrollment Manager Amendment Reason dropdown — exact text from live EM recording.
    (Screen recording April 2026. Multi-select supported in EM.)

    Note: Graduation and Termination are CHECKBOXES in EM, not amendment reasons.
    When generating an amendment for a graduation event, use OTHER here and set
    the Graduation checkbox in the EM submission payload.

    IHL schools (like SDSU): WITHDREW_NCD is not applicable — clock-hour programs only.
    UNSATISFACTORY requires a specific PS conduct/attendance flag — not auto-detected.
    """
    NEVER_ATTENDED            = "Pre-registered but never attended"
    UNSATISFACTORY            = "Unsatisfactory attendance, progress or conduct"
    WITHDREW_BEFORE_TERM      = "Withdraw before beginning of term"
    WITHDREW_POST_DROP_NONPUN = "Withdraw after drop period - non-punitive grades assigned"
    WITHDREW_POST_DROP_PUN    = "Withdraw after drop period - punitive grades assigned"
    WITHDREW_DROP_PERIOD      = "Withdraw during drop period"
    WITHDREW_NCD              = "Withdrawal or interruption (Non-College Degree Programs not on a term basis)"
    OTHER                     = "Other"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EnrolledCourse:
    """A course in a snapshot (minimal representation)."""
    course_id: str
    title: str
    units: float
    modality: Modality  # From original certification
    status: CourseEnrollmentStatus  # Current status


@dataclass
class EnrollmentSnapshot:
    """
    Represents a student's enrollment state at a point in time.

    Captured from PeopleSoft STDNT_ENRL table:
      - snapshot_timestamp: LAST_UPD_DT_STMP (when this snapshot was taken)
      - courses: current enrolled/dropped/withdrawn courses
      - last_certified: the most recent DecisionTreeOutput (from when it was submitted to VA)
      - program: student's current program/major declaration (for program change detection)
      - graduated: True if degree has been conferred in this snapshot
    """
    student_id: str
    facility_code: str
    term: str
    snapshot_timestamp: datetime

    courses: list = field(default_factory=list)  # list of EnrolledCourse
    last_certified: Optional[DecisionTreeOutput] = None  # Most recent certification
    program: Optional[str] = None  # e.g. "B.A. Journalism", used for program change detection
    graduated: bool = False  # True if degree conferred


@dataclass
class EnrollmentChange:
    """
    A single detected change in enrollment.

    Attributes:
      change_type: What changed (COURSE_ADDED, COURSE_DROPPED, etc.)
      course_id: The course affected (if applicable)
      old_value: Previous state (e.g., units, status, program)
      new_value: Current state
      requires_amendment: True if this change triggers an amendment to VA
    """
    student_id: str
    term: str
    change_type: ChangeType
    timestamp: datetime

    course_id: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    requires_amendment: bool = False


@dataclass
class AmendmentRecord:
    """
    A generated amendment to be submitted to VA.

    Contains:
      - The original certification (what we submitted to VA)
      - The revised certification (re-run Decision Tree on modified schedule)
      - The delta (what changed in units, tuition, courses)
      - Submission status (pending_review, approved, submitted)
    """
    student_id: str
    term: str
    reason: AmendmentReason

    original_certification: DecisionTreeOutput
    revised_certification: DecisionTreeOutput

    # Delta between original and revised
    delta: dict = field(default_factory=dict)  # e.g. {"units_before": 12, "units_after": 9, "residential_before": 6, ...}

    # Status tracking
    status: str = "pending_review"  # pending_review, approved, submitted
    hitl_required: bool = False  # Does this need SCO review before submission?

    # Audit trail
    created_timestamp: Optional[datetime] = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Change Detection
# ---------------------------------------------------------------------------

def detect_changes(
    old_snapshot: EnrollmentSnapshot,
    new_snapshot: EnrollmentSnapshot,
) -> list[EnrollmentChange]:
    """
    Compare two enrollment snapshots and return all detected changes.

    Logic:
      - Courses in new but not old → COURSE_ADDED
      - Courses in old but not new (with ENROLLED status) → COURSE_DROPPED
      - Courses with WITHDRAWN status in new but ENROLLED in old → COURSE_WITHDRAWN
      - Same course with different units → UNITS_CHANGED
      - Different program declaration → PROGRAM_CHANGED (requires WEAMS re-match)
      - Degree conferred → GRADUATION

    Returns a list of EnrollmentChange objects, some of which have
    requires_amendment=True.
    """

    changes = []

    # Build maps for easy lookup
    old_courses = {c.course_id: c for c in old_snapshot.courses}
    new_courses = {c.course_id: c for c in new_snapshot.courses}

    # Track which amendments are required
    # A change requires amendment if it affects certifiable units or status

    # 1. COURSE_ADDED
    for course_id, new_course in new_courses.items():
        if course_id not in old_courses:
            change = EnrollmentChange(
                student_id=new_snapshot.student_id,
                term=new_snapshot.term,
                change_type=ChangeType.COURSE_ADDED,
                timestamp=new_snapshot.snapshot_timestamp,
                course_id=course_id,
                new_value=f"{new_course.units} units",
                requires_amendment=False,  # New courses don't affect prior cert
            )
            changes.append(change)

    # 2. COURSE_DROPPED, COURSE_WITHDRAWN, UNITS_CHANGED
    for course_id, old_course in old_courses.items():
        if course_id not in new_courses:
            # Course completely removed from schedule (dropped before certification)
            change = EnrollmentChange(
                student_id=old_snapshot.student_id,
                term=old_snapshot.term,
                change_type=ChangeType.COURSE_DROPPED,
                timestamp=new_snapshot.snapshot_timestamp,
                course_id=course_id,
                old_value=f"{old_course.status.value}, {old_course.units} units",
                requires_amendment=True,  # Dropping a course triggers amendment
            )
            changes.append(change)
        else:
            new_course = new_courses[course_id]

            # Check status change
            if old_course.status != new_course.status:
                if (old_course.status == CourseEnrollmentStatus.ENROLLED and
                    new_course.status == CourseEnrollmentStatus.WITHDRAWN):
                    change = EnrollmentChange(
                        student_id=old_snapshot.student_id,
                        term=old_snapshot.term,
                        change_type=ChangeType.COURSE_WITHDRAWN,
                        timestamp=new_snapshot.snapshot_timestamp,
                        course_id=course_id,
                        old_value=old_course.status.value,
                        new_value=new_course.status.value,
                        requires_amendment=True,
                    )
                    changes.append(change)

            # Check units change
            if old_course.units != new_course.units:
                change = EnrollmentChange(
                    student_id=old_snapshot.student_id,
                    term=old_snapshot.term,
                    change_type=ChangeType.UNITS_CHANGED,
                    timestamp=new_snapshot.snapshot_timestamp,
                    course_id=course_id,
                    old_value=str(old_course.units),
                    new_value=str(new_course.units),
                    requires_amendment=True,
                )
                changes.append(change)

    # 3. PROGRAM_CHANGED
    old_program = old_snapshot.program or (old_snapshot.last_certified.program if old_snapshot.last_certified else None)
    new_program = new_snapshot.program
    if old_program and new_program and old_program != new_program:
        change = EnrollmentChange(
            student_id=new_snapshot.student_id,
            term=new_snapshot.term,
            change_type=ChangeType.PROGRAM_CHANGED,
            timestamp=new_snapshot.snapshot_timestamp,
            old_value=old_program,
            new_value=new_program,
            requires_amendment=True,  # Program change requires re-certification
        )
        changes.append(change)

    # 4. GRADUATION
    if new_snapshot.graduated and not old_snapshot.graduated:
        change = EnrollmentChange(
            student_id=new_snapshot.student_id,
            term=new_snapshot.term,
            change_type=ChangeType.GRADUATION,
            timestamp=new_snapshot.snapshot_timestamp,
            old_value="not_graduated",
            new_value="graduated",
            requires_amendment=True,  # Graduation requires final amendment
        )
        changes.append(change)

    return changes


# ---------------------------------------------------------------------------
# Amendment Generation
# ---------------------------------------------------------------------------

def generate_amendment(
    change: EnrollmentChange,
    old_snapshot: EnrollmentSnapshot,
    new_snapshot: EnrollmentSnapshot,
    student_input: StudentInput,
) -> Optional[AmendmentRecord]:
    """
    Generate an AmendmentRecord from an enrollment change.

    Logic:
      1. Get the original certification (old_snapshot.last_certified)
      2. Build a modified StudentInput based on new_snapshot.courses (and updated program if PROGRAM_CHANGED)
      3. Re-run the Decision Tree on the modified input
      4. Compare old vs. new certification results
      5. Map the change_type to AmendmentReason
      6. Emit an AmendmentRecord

    Special handling:
      - PROGRAM_CHANGED: Updates the program field in modified_student, triggers WEAMS re-match
      - GRADUATION: Still includes courses, but amendment reflects final state

    Returns None if the change doesn't require amendment.
    """

    if not change.requires_amendment:
        return None

    if old_snapshot.last_certified is None:
        return None  # Can't amend without a prior certification

    # Convert new_snapshot courses back to CourseSchedule objects
    # (This mirrors the original student input, but with updated status)
    modified_courses = []
    for snap_course in new_snapshot.courses:
        # Only include ENROLLED courses in the amended certification
        if snap_course.status == CourseEnrollmentStatus.ENROLLED:
            # We need to reconstruct CourseSchedule from the snapshot
            # For now, we'll keep the original schedule data where available
            modified_courses.append(
                CourseSchedule(
                    course_id=snap_course.course_id,
                    title=snap_course.title,
                    units=snap_course.units,
                    # Preserve all the original course metadata from student_input
                    grading_basis=_get_course_grading_basis(student_input, snap_course.course_id),
                    is_remedial=_is_course_remedial(student_input, snap_course.course_id),
                    in_dars=_is_in_dars(student_input, snap_course.course_id),
                    dars_rationale=_get_dars_rationale(student_input, snap_course.course_id),
                    has_in_person_session=_has_in_person(student_input, snap_course.course_id),
                    all_online=snap_course.modality == Modality.DISTANCE,
                    is_pre_term_only=_is_pre_term_only(student_input, snap_course.course_id),
                    is_practicum=_is_practicum(student_input, snap_course.course_id),
                    previously_passed=_was_previously_passed(student_input, snap_course.course_id),
                    repeat_exception=_has_repeat_exception(student_input, snap_course.course_id),
                    has_sco_exception=_has_sco_exception(student_input, snap_course.course_id),
                    sco_exception_type=_get_sco_exception_type(student_input, snap_course.course_id),
                )
            )

    # Create modified student input
    # If PROGRAM_CHANGED, use the new program; otherwise keep the original
    modified_program = (
        new_snapshot.program if change.change_type == ChangeType.PROGRAM_CHANGED
        else student_input.program
    )

    modified_student = StudentInput(
        name=student_input.name,
        student_id=student_input.student_id,
        program=modified_program,
        academic_level=student_input.academic_level,
        benefit_chapter=student_input.benefit_chapter,
        term=student_input.term,
        courses=modified_courses,
        facility_code=student_input.facility_code,
        enrolled_in_799a=student_input.enrolled_in_799a,
        enrolled_in_897=student_input.enrolled_in_897,
        enrolled_in_899=student_input.enrolled_in_899,
    )

    # Re-run Decision Tree on modified enrollment
    revised_certification = run_decision_tree(modified_student)

    # Map change_type to amendment reason (date-aware, uses academic calendar)
    cal = SDSU_FALL_2026  # TODO: look up by term/facility_code once multi-institution
    amendment_reason = _map_change_to_reason(
        change, old_snapshot, new_snapshot,
        revised_certification=revised_certification,
        academic_calendar=cal,
    )

    # Compute the delta
    delta = {
        "original_enrolled_units": old_snapshot.last_certified.total_enrolled_units,
        "revised_enrolled_units": revised_certification.total_enrolled_units,
        "original_certifiable_units": old_snapshot.last_certified.total_certifiable_units,
        "revised_certifiable_units": revised_certification.total_certifiable_units,
        "original_residential": old_snapshot.last_certified.residential_units,
        "revised_residential": revised_certification.residential_units,
        "original_distance": old_snapshot.last_certified.distance_units,
        "revised_distance": revised_certification.distance_units,
        "original_training_time": old_snapshot.last_certified.training_time.value if old_snapshot.last_certified.training_time else None,
        "revised_training_time": revised_certification.training_time.value if revised_certification.training_time else None,
        "original_rate_of_pursuit": old_snapshot.last_certified.rate_of_pursuit,
        "revised_rate_of_pursuit": revised_certification.rate_of_pursuit,
        "changed_course_id": change.course_id,
    }

    # Add program-change-specific or graduation-specific delta fields
    if change.change_type == ChangeType.PROGRAM_CHANGED:
        delta["original_program"] = change.old_value
        delta["revised_program"] = change.new_value
    elif change.change_type == ChangeType.GRADUATION:
        delta["graduation_date"] = new_snapshot.snapshot_timestamp.date().isoformat()

    # Determine if HITL is required
    hitl_required = _should_require_hitl(change, old_snapshot, revised_certification, cal)

    notes = f"Amendment triggered by {change.change_type.value}"
    if change.course_id:
        notes += f": {change.course_id}"
    if change.change_type == ChangeType.PROGRAM_CHANGED:
        notes += f" (program: {change.old_value} → {change.new_value})"
    elif change.change_type == ChangeType.GRADUATION:
        notes += f" (conferral date: {new_snapshot.snapshot_timestamp.date()})"

    amendment = AmendmentRecord(
        student_id=old_snapshot.student_id,
        term=old_snapshot.term,
        reason=amendment_reason,
        original_certification=old_snapshot.last_certified,
        revised_certification=revised_certification,
        delta=delta,
        status="pending_review",
        hitl_required=hitl_required,
        created_timestamp=new_snapshot.snapshot_timestamp,
        notes=notes,
    )

    return amendment


def _map_change_to_reason(
    change: EnrollmentChange,
    old_snapshot: EnrollmentSnapshot,
    new_snapshot: EnrollmentSnapshot,
    revised_certification: Optional[DecisionTreeOutput] = None,
    academic_calendar: Optional[dict] = None,
) -> AmendmentReason:
    """
    Map a change type and context to the correct EM amendment reason.

    All 8 EM Amendment Reason options (from live screen recording, April 2026):
      1. NEVER_ATTENDED            — zero certifiable units remain after drop
      2. UNSATISFACTORY            — conduct/attendance issue (requires PS flag; not auto-detected)
      3. WITHDREW_BEFORE_TERM      — drop before instruction begins
      4. WITHDREW_POST_DROP_NONPUN — formal withdrawal after add/drop deadline, non-punitive grade
      5. WITHDREW_POST_DROP_PUN    — formal withdrawal after add/drop deadline, punitive grade
      6. WITHDREW_DROP_PERIOD      — drop during the add/drop window (>= instruction start, <= add/drop deadline)
      7. WITHDREW_NCD              — NCD/clock-hour programs only (not applicable to IHL schools like SDSU)
      8. OTHER                     — program change, graduation, or any unclassified event

    Date-aware logic uses the academic calendar:
      - change_date < instruction_begins         → WITHDREW_BEFORE_TERM
      - instruction_begins <= change_date <= add_drop_deadline → WITHDREW_DROP_PERIOD
      - change_date > add_drop_deadline          → WITHDREW_POST_DROP_NONPUN (non-punitive default;
                                                    SCO can change to punitive at review)

    Graduation: EM uses a CHECKBOX (not a dropdown reason) for graduation/end-of-term.
    Program changes: SCO must verify WEAMS eligibility of new program — reason = OTHER.

    Falls back to SDSU_FALL_2026 calendar if none provided.
    """

    cal = academic_calendar or SDSU_FALL_2026

    # GRADUATION → reason is OTHER; the Graduation checkbox is set separately in EM
    if change.change_type == ChangeType.GRADUATION:
        return AmendmentReason.OTHER

    # PROGRAM_CHANGED → SCO must verify new program; no standard reason fits
    if change.change_type == ChangeType.PROGRAM_CHANGED:
        return AmendmentReason.OTHER

    # NEVER_ATTENDED — ALL certifiable units gone after this change
    if revised_certification and revised_certification.total_certifiable_units == 0:
        return AmendmentReason.NEVER_ATTENDED

    # Date-aware reason mapping for drops, withdrawals, and unit changes
    change_date = change.timestamp.date()
    instruction_begins = cal["instruction_begins"]
    add_drop = cal["add_drop_deadline"]

    if change.change_type in (ChangeType.COURSE_DROPPED, ChangeType.COURSE_WITHDRAWN, ChangeType.UNITS_CHANGED):
        if change_date < instruction_begins:
            return AmendmentReason.WITHDREW_BEFORE_TERM
        elif change_date <= add_drop:
            return AmendmentReason.WITHDREW_DROP_PERIOD
        else:
            # After add/drop deadline: default to non-punitive
            # SCO reviews at HITL step and can change to WITHDREW_POST_DROP_PUN if grade is punitive
            return AmendmentReason.WITHDREW_POST_DROP_NONPUN

    # Default fallback for any unclassified change type
    return AmendmentReason.OTHER


def _should_require_hitl(
    change: EnrollmentChange,
    old_snapshot: EnrollmentSnapshot,
    revised_certification: DecisionTreeOutput,
    academic_calendar: Optional[dict] = None,
) -> bool:
    """
    Determine if an amendment requires Human-In-The-Loop review.

    HITL required if:
      - Zero certifiable units (never attended / total withdrawal)
      - Drop or withdrawal AFTER census date (VA has already counted enrollment;
        overpayment risk — SCO must review before submitting)
      - Training time drops from full-time to anything less
      - SCO queue items in revised certification
      - PROGRAM_CHANGED with LOW or NO WEAMS match (SCO must verify new program is VA-approved)
      - GRADUATION (SCO must verify degree conferral date and that all grades posted)
    """

    cal = academic_calendar or SDSU_FALL_2026

    # PROGRAM_CHANGED or GRADUATION — always HITL (SCO verification required)
    if change.change_type in (ChangeType.PROGRAM_CHANGED, ChangeType.GRADUATION):
        return True

    # SCO queue items trigger HITL
    if revised_certification.sco_queue_items:
        return True

    # Zero certifiable units = never attended / total withdrawal — always HITL
    if revised_certification.total_certifiable_units == 0:
        return True

    # Post-census changes: VA has already "counted" this enrollment.
    # Any reduction after census creates overpayment risk → SCO must review.
    if change.change_type in (ChangeType.COURSE_DROPPED, ChangeType.COURSE_WITHDRAWN,
                               ChangeType.UNITS_CHANGED):
        change_date = change.timestamp.date()
        census = cal.get("census_date")
        if census and change_date > census:
            return True

    # If original was full-time and revised is less than full, flag for HITL
    if old_snapshot.last_certified:
        orig_tt = old_snapshot.last_certified.training_time
        revised_tt = revised_certification.training_time
        if orig_tt == TrainingTime.FULL_TIME and revised_tt != TrainingTime.FULL_TIME:
            return True

    return False


# ---------------------------------------------------------------------------
# Student Input Helper Functions (for re-certification)
# ---------------------------------------------------------------------------
# These functions extract metadata from the original StudentInput
# to use when building the modified schedule for re-certification.

def _get_course_grading_basis(student: StudentInput, course_id: str):
    """Find the original grading basis for a course."""
    for course in student.courses:
        if course.course_id == course_id:
            return course.grading_basis
    return None


def _is_course_remedial(student: StudentInput, course_id: str) -> bool:
    """Check if a course is remedial."""
    for course in student.courses:
        if course.course_id == course_id:
            return course.is_remedial
    return False


def _is_in_dars(student: StudentInput, course_id: str) -> bool:
    """Check if a course is in DARS."""
    for course in student.courses:
        if course.course_id == course_id:
            return course.in_dars
    return False


def _get_dars_rationale(student: StudentInput, course_id: str) -> str:
    """Get DARS rationale."""
    for course in student.courses:
        if course.course_id == course_id:
            return course.dars_rationale
    return ""


def _has_in_person(student: StudentInput, course_id: str) -> bool:
    """Check if course has in-person session."""
    for course in student.courses:
        if course.course_id == course_id:
            return course.has_in_person_session
    return False


def _is_pre_term_only(student: StudentInput, course_id: str) -> bool:
    """Check if course is pre-term only."""
    for course in student.courses:
        if course.course_id == course_id:
            return course.is_pre_term_only
    return False


def _is_practicum(student: StudentInput, course_id: str) -> bool:
    """Check if course is practicum."""
    for course in student.courses:
        if course.course_id == course_id:
            return course.is_practicum
    return False


def _was_previously_passed(student: StudentInput, course_id: str) -> bool:
    """Check if course was previously passed."""
    for course in student.courses:
        if course.course_id == course_id:
            return course.previously_passed
    return False


def _has_repeat_exception(student: StudentInput, course_id: str) -> bool:
    """Check if course has repeat exception."""
    for course in student.courses:
        if course.course_id == course_id:
            return course.repeat_exception
    return False


def _has_sco_exception(student: StudentInput, course_id: str) -> bool:
    """Check if course has SCO exception."""
    for course in student.courses:
        if course.course_id == course_id:
            return course.has_sco_exception
    return False


def _get_sco_exception_type(student: StudentInput, course_id: str) -> str:
    """Get SCO exception type."""
    for course in student.courses:
        if course.course_id == course_id:
            return course.sco_exception_type
    return ""


# ---------------------------------------------------------------------------
# Batch Processing
# ---------------------------------------------------------------------------

def process_enrollment_updates(
    students_with_changes: list[Tuple[StudentInput, EnrollmentSnapshot, EnrollmentSnapshot]],
) -> list[AmendmentRecord]:
    """
    Batch processor for enrollment changes.

    Input: List of (student_input, old_snapshot, new_snapshot) tuples

    For each student:
      1. Detect changes between old and new snapshots
      2. For each change that requires amendment, generate an AmendmentRecord
      3. Return all amendments

    This is what the dashboard calls to process bulk updates.
    """

    amendments = []

    for student_input, old_snapshot, new_snapshot in students_with_changes:
        changes = detect_changes(old_snapshot, new_snapshot)

        for change in changes:
            if change.requires_amendment:
                amendment = generate_amendment(change, old_snapshot, new_snapshot, student_input)
                if amendment:
                    amendments.append(amendment)

    return amendments


# ---------------------------------------------------------------------------
# Test: James Roster Amendment
# ---------------------------------------------------------------------------

def james_roster_amendment_test():
    """
    Test the amendment engine with James Roster's enrollment.

    Scenario:
      1. James originally certified with R:6 D:6 T:12 (5 courses, ENS 331 excluded)
      2. James drops MIS 460 (3 residential units)
      3. Amendment engine detects the drop and re-certifies
      4. Revised: R:3 D:6 T:9, training time drops to THREE_QUARTER
      5. Amendment is marked REDUCED_ENROLLMENT

    Expected deltas:
      - Certifiable units: 12 → 9
      - Residential: 6 → 3
      - Distance: 6 → 6 (unchanged)
      - Training time: FULL_TIME → THREE_QUARTER
      - RoP: 1.0 → 0.75
    """

    from datetime import date
    from decision_tree import (
        GradingBasis,
        AcademicLevel,
    )

    print("\n" + "=" * 70)
    print("  JAMES ROSTER AMENDMENT TEST")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # Step 1: Create original student input and certification
    # -----------------------------------------------------------------------
    print("\n>>> STEP 1: Original Certification (James Roster, Fall 2024)\n")

    original_student = StudentInput(
        name="Daniel Bahena",
        student_id="NF-001",
        program="B.A. Journalism",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2024",
        courses=[
            CourseSchedule(
                course_id="ENS 331",
                title="Environmental Science",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=False,
                all_online=True,
                has_in_person_session=False,
            ),
            CourseSchedule(
                course_id="MIS 401",
                title="Management Information Systems",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                all_online=False,
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="MIS 460",
                title="Business Application Development",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                all_online=False,
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="MIS 585",
                title="Electronic Commerce Strategy",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                all_online=True,
                has_in_person_session=False,
            ),
            CourseSchedule(
                course_id="MUSIC 151",
                title="Introduction to Music",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="GE area",
                all_online=True,
                has_in_person_session=False,
            ),
        ],
    )

    original_certification = run_decision_tree(original_student)

    print(f"  Original Certification Results:")
    print(f"    Certifiable units: {original_certification.total_certifiable_units:.1f}")
    print(f"    Residential: {original_certification.residential_units:.1f}")
    print(f"    Distance: {original_certification.distance_units:.1f}")
    print(f"    Training time: {original_certification.training_time.value.replace('_', ' ').title()}")
    print(f"    Rate of pursuit: {original_certification.rate_of_pursuit:.0%}")

    # Create old snapshot with the original certification
    # Note: student/term IDs say "Fall 2024" but timestamps use 2026 so the
    # SDSU_FALL_2026 academic calendar date logic works correctly.
    old_snapshot = EnrollmentSnapshot(
        student_id="NF-001",
        facility_code="11910105",
        term="Fall 2024",
        snapshot_timestamp=datetime(2026, 8, 24, 10, 0, 0),  # instruction begins
        courses=[
            EnrolledCourse(
                course_id="ENS 331",
                title="Environmental Science",
                units=3.0,
                modality=Modality.DISTANCE,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="MIS 401",
                title="Management Information Systems",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="MIS 460",
                title="Business Application Development",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="MIS 585",
                title="Electronic Commerce Strategy",
                units=3.0,
                modality=Modality.DISTANCE,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="MUSIC 151",
                title="Introduction to Music",
                units=3.0,
                modality=Modality.DISTANCE,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
        ],
        last_certified=original_certification,
    )

    # -----------------------------------------------------------------------
    # Step 2: Simulate MIS 460 drop
    # -----------------------------------------------------------------------
    print("\n>>> STEP 2: MIS 460 Dropped (Week 2 of term)\n")

    new_snapshot = EnrollmentSnapshot(
        student_id="NF-001",
        facility_code="11910105",
        term="Fall 2024",
        snapshot_timestamp=datetime(2026, 9, 2, 14, 30, 0),  # week 2 — before add/drop deadline (Sept 4)
        courses=[
            EnrolledCourse(
                course_id="ENS 331",
                title="Environmental Science",
                units=3.0,
                modality=Modality.DISTANCE,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="MIS 401",
                title="Management Information Systems",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            # MIS 460 is now dropped (removed from new snapshot)
            EnrolledCourse(
                course_id="MIS 585",
                title="Electronic Commerce Strategy",
                units=3.0,
                modality=Modality.DISTANCE,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="MUSIC 151",
                title="Introduction to Music",
                units=3.0,
                modality=Modality.DISTANCE,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
        ],
        last_certified=original_certification,  # Still have the original cert
    )

    # -----------------------------------------------------------------------
    # Step 3: Detect changes
    # -----------------------------------------------------------------------
    print("\n>>> STEP 3: Change Detection\n")

    changes = detect_changes(old_snapshot, new_snapshot)
    print(f"  Detected {len(changes)} change(s):")
    for change in changes:
        print(f"    - {change.change_type.value}: {change.course_id}")
        print(f"      Old: {change.old_value} → New: {change.new_value}")
        print(f"      Requires amendment: {change.requires_amendment}")

    # -----------------------------------------------------------------------
    # Step 4: Generate amendment
    # -----------------------------------------------------------------------
    print("\n>>> STEP 4: Amendment Generation\n")

    amendments = []
    for change in changes:
        amendment = generate_amendment(change, old_snapshot, new_snapshot, original_student)
        if amendment:
            amendments.append(amendment)

    if amendments:
        amendment = amendments[0]
        print(f"  Amendment Record Generated:")
        print(f"    Reason: {amendment.reason.value}")
        print(f"    Status: {amendment.status}")
        print(f"    HITL required: {amendment.hitl_required}")
        print(f"\n  DELTAS:")
        print(f"    Certifiable units: {amendment.delta['original_certifiable_units']:.1f} → {amendment.delta['revised_certifiable_units']:.1f}")
        print(f"    Residential: {amendment.delta['original_residential']:.1f} → {amendment.delta['revised_residential']:.1f}")
        print(f"    Distance: {amendment.delta['original_distance']:.1f} → {amendment.delta['revised_distance']:.1f}")
        print(f"    Training time: {amendment.delta['original_training_time']} → {amendment.delta['revised_training_time']}")
        print(f"    Rate of pursuit: {amendment.delta['original_rate_of_pursuit']:.0%} → {amendment.delta['revised_rate_of_pursuit']:.0%}")
        print(f"    Changed course: {amendment.delta['changed_course_id']}")

    # -----------------------------------------------------------------------
    # REGRESSION CHECK
    # -----------------------------------------------------------------------
    print("\n  REGRESSION CHECK:")

    checks_passed = 0
    checks_total = 0

    def check(description, actual, expected):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            checks_passed += 1
        print(f"    [{status}] {description}: expected={expected}, got={actual}")

    # Original certification baseline
    check("Original certifiable units", original_certification.total_certifiable_units, 12.0)
    check("Original residential units", original_certification.residential_units, 6.0)
    check("Original distance units", original_certification.distance_units, 6.0)
    check("Original training time", original_certification.training_time, TrainingTime.FULL_TIME)
    check("Original RoP", original_certification.rate_of_pursuit, 1.0)

    # Changes detected
    check("Number of changes detected", len(changes), 1)
    if changes:
        check("Change type", changes[0].change_type, ChangeType.COURSE_DROPPED)
        check("Changed course ID", changes[0].course_id, "MIS 460")
        check("Requires amendment", changes[0].requires_amendment, True)

    # Amendment generated
    check("Number of amendments", len(amendments), 1)

    if amendments:
        amendment = amendments[0]
        revised = amendment.revised_certification

        # Revised certification deltas
        check("Revised certifiable units", revised.total_certifiable_units, 9.0)
        check("Revised residential units", revised.residential_units, 3.0)
        check("Revised distance units", revised.distance_units, 6.0)
        check("Revised training time", revised.training_time, TrainingTime.THREE_QUARTER)
        check("Revised RoP", revised.rate_of_pursuit, 0.75)

        # Drop on Sept 2, 2026 — after instruction begins (Aug 24) and before add/drop deadline (Sept 4)
        check("Amendment reason", amendment.reason, AmendmentReason.WITHDREW_DROP_PERIOD)

        # Delta values
        check("Delta original certifiable", amendment.delta['original_certifiable_units'], 12.0)
        check("Delta revised certifiable", amendment.delta['revised_certifiable_units'], 9.0)
        check("Delta original residential", amendment.delta['original_residential'], 6.0)
        check("Delta revised residential", amendment.delta['revised_residential'], 3.0)

    print(f"\n    {checks_passed}/{checks_total} checks passed.")

    if checks_passed == checks_total:
        print("\n    *** JAMES ROSTER AMENDMENT TEST: ALL CHECKS PASSED ***\n")
        return True
    else:
        print(f"\n    *** JAMES ROSTER AMENDMENT TEST: {checks_total - checks_passed} FAILURES ***\n")
        return False


# ---------------------------------------------------------------------------
# Test 2: Course Withdrawal AFTER Add/Drop Deadline
# ---------------------------------------------------------------------------

def withdrawal_after_deadline_test():
    """
    Test: Student withdraws a course AFTER the add/drop deadline.

    Scenario (SDSU Fall 2026):
      - Sarah Kim originally certified with 3 courses (10 units, three-quarter)
      - On October 15 (well after Sept 4 add/drop deadline), she withdraws PSY 450
      - Amendment reason should be WITHDREW_DROP_PERIOD (not REDUCED_ENROLLMENT)
      - Revised: 7 units, half-time

    This tests the date-aware amendment reason mapping.
    """

    from decision_tree import GradingBasis, AcademicLevel

    print("\n" + "=" * 70)
    print("  WITHDRAWAL AFTER ADD/DROP DEADLINE TEST")
    print("  (SDSU Fall 2026: add/drop deadline = Sept 4, 2026)")
    print("=" * 70)

    # Sarah Kim's original schedule
    original_student = StudentInput(
        name="Sarah Kim",
        student_id="SK-004",
        program="B.A. Psychology",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11918105",  # CSUN but using SDSU calendar for dates
        courses=[
            CourseSchedule(
                course_id="PSY 310",
                title="Developmental Psychology",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="PSY 380",
                title="Research Methods",
                units=4.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="PSY 450",
                title="Abnormal Psychology",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
        ],
    )

    original_cert = run_decision_tree(original_student)

    # Original snapshot: certified Aug 25 (day after instruction begins)
    old_snapshot = EnrollmentSnapshot(
        student_id="SK-004",
        facility_code="11918105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 8, 25, 10, 0, 0),
        courses=[
            EnrolledCourse(course_id="PSY 310", title="Developmental Psychology",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="PSY 380", title="Research Methods",
                           units=4.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="PSY 450", title="Abnormal Psychology",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
        ],
        last_certified=original_cert,
    )

    # New snapshot: Oct 15 — PSY 450 status changed to WITHDRAWN
    # (after add/drop deadline of Sept 4)
    new_snapshot = EnrollmentSnapshot(
        student_id="SK-004",
        facility_code="11918105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 10, 15, 9, 0, 0),
        courses=[
            EnrolledCourse(course_id="PSY 310", title="Developmental Psychology",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="PSY 380", title="Research Methods",
                           units=4.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="PSY 450", title="Abnormal Psychology",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.WITHDRAWN),
        ],
        last_certified=original_cert,
    )

    changes = detect_changes(old_snapshot, new_snapshot)
    amendments = []
    for change in changes:
        amendment = generate_amendment(change, old_snapshot, new_snapshot, original_student)
        if amendment:
            amendments.append(amendment)

    # Regression checks
    print("\n  REGRESSION CHECK:")
    checks_passed = 0
    checks_total = 0

    def check(description, actual, expected):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            checks_passed += 1
        print(f"    [{status}] {description}: expected={expected}, got={actual}")

    check("Original certifiable units", original_cert.total_certifiable_units, 10.0)
    check("Original training time", original_cert.training_time, TrainingTime.THREE_QUARTER)
    check("Number of changes", len(changes), 1)
    if changes:
        check("Change type", changes[0].change_type, ChangeType.COURSE_WITHDRAWN)
        check("Changed course", changes[0].course_id, "PSY 450")
    check("Number of amendments", len(amendments), 1)
    if amendments:
        a = amendments[0]
        check("Revised certifiable units", a.revised_certification.total_certifiable_units, 7.0)
        check("Revised training time", a.revised_certification.training_time, TrainingTime.HALF_TIME)
        # KEY CHECK: Oct 15 > add/drop deadline (Sept 4) → WITHDREW_POST_DROP_NONPUN
        # (non-punitive default; SCO changes to punitive at HITL review if grade warrants)
        check("Amendment reason", a.reason, AmendmentReason.WITHDREW_POST_DROP_NONPUN)
        # Oct 15 is AFTER census (Sept 21) → HITL required (overpayment risk)
        check("HITL required (post-census withdrawal)", a.hitl_required, True)

    print(f"\n    {checks_passed}/{checks_total} checks passed.")
    passed = checks_passed == checks_total
    if passed:
        print("\n    *** WITHDRAWAL AFTER DEADLINE TEST: ALL CHECKS PASSED ***\n")
    else:
        print(f"\n    *** WITHDRAWAL AFTER DEADLINE TEST: {checks_total - checks_passed} FAILURES ***\n")
    return passed


# ---------------------------------------------------------------------------
# Test 3: Course Add (should NOT trigger amendment)
# ---------------------------------------------------------------------------

def course_add_no_amendment_test():
    """
    Test: Student adds a course AFTER initial certification.

    Scenario (SDSU Fall 2026):
      - Daniel Bahena certified with 4 courses (12 units, full-time)
      - On Aug 28 (during add/drop period), he adds JOUR 210
      - A course ADD does not affect the prior certification
      - The change should be detected but requires_amendment = False
      - No amendment should be generated

    This tests that adds are tracked but don't create false amendments.
    """

    from decision_tree import GradingBasis, AcademicLevel

    print("\n" + "=" * 70)
    print("  COURSE ADD — NO AMENDMENT TEST")
    print("  (SDSU Fall 2026: add during add/drop period)")
    print("=" * 70)

    original_student = StudentInput(
        name="Daniel Bahena",
        student_id="DB-001",
        program="B.A. Journalism",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11910105",
        courses=[
            CourseSchedule(course_id="JOUR 301", title="Reporting and Writing", units=3.0,
                           grading_basis=GradingBasis.LETTER, in_dars=True, dars_rationale="major requirement",
                           has_in_person_session=True, all_online=False),
            CourseSchedule(course_id="JOUR 350", title="Digital Media Production", units=3.0,
                           grading_basis=GradingBasis.LETTER, in_dars=True, dars_rationale="major requirement",
                           has_in_person_session=True, all_online=False),
            CourseSchedule(course_id="JOUR 400", title="Ethics in Journalism", units=3.0,
                           grading_basis=GradingBasis.LETTER, in_dars=True, dars_rationale="major requirement",
                           has_in_person_session=True, all_online=False),
            CourseSchedule(course_id="COMM 200", title="Communication Theory", units=3.0,
                           grading_basis=GradingBasis.LETTER, in_dars=True, dars_rationale="major requirement",
                           has_in_person_session=True, all_online=False),
        ],
    )

    original_cert = run_decision_tree(original_student)

    # Certified on Aug 24 (first day of classes)
    old_snapshot = EnrollmentSnapshot(
        student_id="DB-001",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 8, 24, 10, 0, 0),
        courses=[
            EnrolledCourse(course_id="JOUR 301", title="Reporting and Writing",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="JOUR 350", title="Digital Media Production",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="JOUR 400", title="Ethics in Journalism",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="COMM 200", title="Communication Theory",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
        ],
        last_certified=original_cert,
    )

    # Aug 28: student adds JOUR 210 (during add/drop period)
    new_snapshot = EnrollmentSnapshot(
        student_id="DB-001",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 8, 28, 14, 0, 0),
        courses=[
            EnrolledCourse(course_id="JOUR 301", title="Reporting and Writing",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="JOUR 350", title="Digital Media Production",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="JOUR 400", title="Ethics in Journalism",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="COMM 200", title="Communication Theory",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            # NEW COURSE ADDED
            EnrolledCourse(course_id="JOUR 210", title="Intro to Photojournalism",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
        ],
        last_certified=original_cert,
    )

    changes = detect_changes(old_snapshot, new_snapshot)
    amendments = []
    for change in changes:
        amendment = generate_amendment(change, old_snapshot, new_snapshot, original_student)
        if amendment:
            amendments.append(amendment)

    print("\n  REGRESSION CHECK:")
    checks_passed = 0
    checks_total = 0

    def check(description, actual, expected):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            checks_passed += 1
        print(f"    [{status}] {description}: expected={expected}, got={actual}")

    check("Number of changes detected", len(changes), 1)
    if changes:
        check("Change type", changes[0].change_type, ChangeType.COURSE_ADDED)
        check("Added course", changes[0].course_id, "JOUR 210")
        check("Requires amendment", changes[0].requires_amendment, False)
    check("Number of amendments generated", len(amendments), 0)

    print(f"\n    {checks_passed}/{checks_total} checks passed.")
    passed = checks_passed == checks_total
    if passed:
        print("\n    *** COURSE ADD NO AMENDMENT TEST: ALL CHECKS PASSED ***\n")
    else:
        print(f"\n    *** COURSE ADD NO AMENDMENT TEST: {checks_total - checks_passed} FAILURES ***\n")
    return passed


# ---------------------------------------------------------------------------
# Test 4: Never Attended (ALL certifiable courses dropped)
# ---------------------------------------------------------------------------

def never_attended_test():
    """
    Test: Student drops ALL courses before census.

    Scenario (SDSU Fall 2026):
      - James Chen certified with 3 courses (9 units, full-time grad)
      - On Sept 1 (before add/drop deadline Sept 4), he drops ALL courses
      - Amendment reason: NEVER_ATTENDED (0 certifiable units remain)
      - HITL required: True (full-time → nothing)

    This tests the "never attended" edge case.
    """

    from decision_tree import GradingBasis, AcademicLevel

    print("\n" + "=" * 70)
    print("  NEVER ATTENDED TEST (ALL COURSES DROPPED)")
    print("  (SDSU Fall 2026: drop before add/drop deadline)")
    print("=" * 70)

    original_student = StudentInput(
        name="James Chen",
        student_id="JC-003",
        program="M.C.P. City Planning",
        academic_level=AcademicLevel.MASTERS,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11910105",
        enrolled_in_799a=True,
        courses=[
            CourseSchedule(course_id="CP 501", title="Urban Planning Theory", units=3.0,
                           grading_basis=GradingBasis.LETTER, in_dars=True, dars_rationale="major requirement",
                           has_in_person_session=True, all_online=False),
            CourseSchedule(course_id="CP 520", title="Planning Methods", units=3.0,
                           grading_basis=GradingBasis.LETTER, in_dars=True, dars_rationale="major requirement",
                           has_in_person_session=True, all_online=False),
            CourseSchedule(course_id="CP 799A", title="Thesis", units=3.0,
                           grading_basis=GradingBasis.LETTER, in_dars=True, dars_rationale="major requirement",
                           has_in_person_session=False, all_online=True),
        ],
    )

    original_cert = run_decision_tree(original_student)

    # Certified Aug 25
    old_snapshot = EnrollmentSnapshot(
        student_id="JC-003",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 8, 25, 10, 0, 0),
        courses=[
            EnrolledCourse(course_id="CP 501", title="Urban Planning Theory",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="CP 520", title="Planning Methods",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="CP 799A", title="Thesis",
                           units=3.0, modality=Modality.DISTANCE, status=CourseEnrollmentStatus.ENROLLED),
        ],
        last_certified=original_cert,
    )

    # Sept 1: ALL courses dropped (before add/drop deadline Sept 4)
    new_snapshot = EnrollmentSnapshot(
        student_id="JC-003",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 9, 1, 11, 0, 0),
        courses=[],  # Everything dropped
        last_certified=original_cert,
    )

    changes = detect_changes(old_snapshot, new_snapshot)
    amendments = []
    for change in changes:
        amendment = generate_amendment(change, old_snapshot, new_snapshot, original_student)
        if amendment:
            amendments.append(amendment)

    print("\n  REGRESSION CHECK:")
    checks_passed = 0
    checks_total = 0

    def check(description, actual, expected):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            checks_passed += 1
        print(f"    [{status}] {description}: expected={expected}, got={actual}")

    check("Original certifiable units", original_cert.total_certifiable_units, 9.0)
    check("Original training time", original_cert.training_time, TrainingTime.FULL_TIME)
    check("Number of changes detected", len(changes), 3)  # 3 courses dropped

    # All 3 changes should require amendment
    amendment_changes = [c for c in changes if c.requires_amendment]
    check("Changes requiring amendment", len(amendment_changes), 3)

    # Should generate 3 amendments, but the FIRST one that produces 0 units
    # triggers NEVER_ATTENDED
    check("Amendments generated", len(amendments), 3)

    if amendments:
        # The first amendment that encounters 0 certifiable units should be NEVER_ATTENDED
        # (Each drop is processed independently — each one re-runs the DT on the
        # snapshot's remaining courses, which is 0 for all of them since the new
        # snapshot has no courses)
        never_attended_count = sum(1 for a in amendments if a.reason == AmendmentReason.NEVER_ATTENDED)
        check("NEVER_ATTENDED amendments", never_attended_count, 3)

        # Check first amendment details
        a = amendments[0]
        check("Revised certifiable units", a.revised_certification.total_certifiable_units, 0)
        check("HITL required", a.hitl_required, True)

    print(f"\n    {checks_passed}/{checks_total} checks passed.")
    passed = checks_passed == checks_total
    if passed:
        print("\n    *** NEVER ATTENDED TEST: ALL CHECKS PASSED ***\n")
    else:
        print(f"\n    *** NEVER ATTENDED TEST: {checks_total - checks_passed} FAILURES ***\n")
    return passed


# ---------------------------------------------------------------------------
# Test 5: Unit Change on Existing Course
# ---------------------------------------------------------------------------

def unit_change_test():
    """
    Test: A course's unit count changes after certification.

    Scenario (SDSU Fall 2026):
      - Robert Torres certified with 3 courses (10 units, three-quarter)
      - On Sept 2 (before add/drop), CE 310 changes from 4 units to 3 units
        (e.g., lab section dropped, lecture remains)
      - Amendment: REDUCED_ENROLLMENT, 10→9 units
      - Training time stays THREE_QUARTER (9 units undergrad)

    This tests unit change detection on an existing course.
    """

    from decision_tree import GradingBasis, AcademicLevel

    print("\n" + "=" * 70)
    print("  UNIT CHANGE TEST")
    print("  (SDSU Fall 2026: unit change before add/drop deadline)")
    print("=" * 70)

    original_student = StudentInput(
        name="Robert Torres",
        student_id="RT-005",
        program="B.S. Civil Engineering",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch31",
        term="Fall 2026",
        facility_code="11918105",
        courses=[
            CourseSchedule(course_id="CE 310", title="Structural Analysis", units=4.0,
                           grading_basis=GradingBasis.LETTER, in_dars=True, dars_rationale="major requirement",
                           has_in_person_session=True, all_online=False),
            CourseSchedule(course_id="CE 330", title="Hydraulics and Water Resources", units=3.0,
                           grading_basis=GradingBasis.LETTER, in_dars=True, dars_rationale="major requirement",
                           has_in_person_session=True, all_online=False),
            CourseSchedule(course_id="CE 410", title="Transportation Engineering", units=3.0,
                           grading_basis=GradingBasis.LETTER, in_dars=True, dars_rationale="major requirement",
                           has_in_person_session=True, all_online=False),
        ],
    )

    original_cert = run_decision_tree(original_student)

    # Certified Aug 25
    old_snapshot = EnrollmentSnapshot(
        student_id="RT-005",
        facility_code="11918105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 8, 25, 10, 0, 0),
        courses=[
            EnrolledCourse(course_id="CE 310", title="Structural Analysis",
                           units=4.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="CE 330", title="Hydraulics and Water Resources",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="CE 410", title="Transportation Engineering",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
        ],
        last_certified=original_cert,
    )

    # Sept 2: CE 310 drops from 4 to 3 units (before add/drop deadline)
    new_snapshot = EnrollmentSnapshot(
        student_id="RT-005",
        facility_code="11918105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 9, 2, 15, 0, 0),
        courses=[
            EnrolledCourse(course_id="CE 310", title="Structural Analysis",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),  # 4→3
            EnrolledCourse(course_id="CE 330", title="Hydraulics and Water Resources",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="CE 410", title="Transportation Engineering",
                           units=3.0, modality=Modality.RESIDENTIAL, status=CourseEnrollmentStatus.ENROLLED),
        ],
        last_certified=original_cert,
    )

    changes = detect_changes(old_snapshot, new_snapshot)
    amendments = []
    for change in changes:
        amendment = generate_amendment(change, old_snapshot, new_snapshot, original_student)
        if amendment:
            amendments.append(amendment)

    print("\n  REGRESSION CHECK:")
    checks_passed = 0
    checks_total = 0

    def check(description, actual, expected):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            checks_passed += 1
        print(f"    [{status}] {description}: expected={expected}, got={actual}")

    check("Original certifiable units", original_cert.total_certifiable_units, 10.0)
    check("Original training time", original_cert.training_time, TrainingTime.THREE_QUARTER)
    check("Number of changes detected", len(changes), 1)
    if changes:
        check("Change type", changes[0].change_type, ChangeType.UNITS_CHANGED)
        check("Changed course", changes[0].course_id, "CE 310")
        check("Old value", changes[0].old_value, "4.0")
        check("New value", changes[0].new_value, "3.0")
    check("Number of amendments", len(amendments), 1)
    if amendments:
        a = amendments[0]
        check("Revised certifiable units", a.revised_certification.total_certifiable_units, 9.0)
        check("Revised training time", a.revised_certification.training_time, TrainingTime.THREE_QUARTER)
        # Sept 2 < add/drop deadline (Sept 4) → WITHDREW_DROP_PERIOD
        check("Amendment reason", a.reason, AmendmentReason.WITHDREW_DROP_PERIOD)
        check("Delta changed course", a.delta['changed_course_id'], "CE 310")
        check("HITL required", a.hitl_required, False)

    print(f"\n    {checks_passed}/{checks_total} checks passed.")
    passed = checks_passed == checks_total
    if passed:
        print("\n    *** UNIT CHANGE TEST: ALL CHECKS PASSED ***\n")
    else:
        print(f"\n    *** UNIT CHANGE TEST: {checks_total - checks_passed} FAILURES ***\n")
    return passed


def post_census_drop_test():
    """
    Test 6: Post-Census Course Drop
    ================================
    Scenario: Alex Rivera (Ch. 33) is full-time at SDSU. On Oct 1, 2026 —
    AFTER the census date (Sept 21) but BEFORE the withdrawal deadline (Nov 1)
    — drops MATH 252 (4 units, residential).

    Expected:
      - Change detected as COURSE_DROPPED
      - Amendment reason: REDUCED_ENROLLMENT (it's a drop, not a formal withdrawal)
      - HITL REQUIRED: YES — post-census, VA has already counted this enrollment,
        potential overpayment that SCO must review before submitting
      - Units: 13 → 9, full-time → three-quarter
    """

    checks_passed = 0
    checks_total = 0

    def check(label, actual, expected):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            checks_passed += 1
        print(f"    [{status}] {label}: expected={expected}, got={actual}")

    from decision_tree import GradingBasis, AcademicLevel

    print("\n" + "=" * 70)
    print("  POST-CENSUS DROP TEST")
    print("  (SDSU Fall 2026: census date = Sept 21, 2026)")
    print("=" * 70)

    # --- Original enrollment: 4 courses, 13 units, full-time ---
    original_courses = [
        CourseSchedule(
            course_id="MATH 252", title="Applied Mathematics II", units=4.0,
            grading_basis=GradingBasis.LETTER, in_dars=True,
            dars_rationale="major requirement",
            all_online=False, has_in_person_session=True,
        ),
        CourseSchedule(
            course_id="CS 310", title="Data Structures", units=3.0,
            grading_basis=GradingBasis.LETTER, in_dars=True,
            dars_rationale="major requirement",
            all_online=False, has_in_person_session=True,
        ),
        CourseSchedule(
            course_id="PHYS 195", title="Physics I", units=3.0,
            grading_basis=GradingBasis.LETTER, in_dars=True,
            dars_rationale="major requirement",
            all_online=True, has_in_person_session=False,
        ),
        CourseSchedule(
            course_id="ENGR 100", title="Intro to Engineering", units=3.0,
            grading_basis=GradingBasis.LETTER, in_dars=True,
            dars_rationale="GE requirement",
            all_online=True, has_in_person_session=False,
        ),
    ]

    original_student = StudentInput(
        name="Alex Rivera", student_id="ARI2026",
        program="B.S. Applied Mathematics",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2026", courses=original_courses,
        facility_code="11910105",
    )
    original_cert = run_decision_tree(original_student)

    old_snapshot = EnrollmentSnapshot(
        student_id="ARI2026",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 8, 24, 8, 0),
        courses=[
            EnrolledCourse(course_id="MATH 252", title="Applied Mathematics II",
                           units=4.0, modality=Modality.RESIDENTIAL,
                           status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="CS 310", title="Data Structures",
                           units=3.0, modality=Modality.RESIDENTIAL,
                           status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="PHYS 195", title="Physics I",
                           units=3.0, modality=Modality.DISTANCE,
                           status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="ENGR 100", title="Intro to Engineering",
                           units=3.0, modality=Modality.DISTANCE,
                           status=CourseEnrollmentStatus.ENROLLED),
        ],
        last_certified=original_cert,
    )

    # --- Oct 1: Alex drops MATH 252 (after census Sept 21) ---
    new_snapshot = EnrollmentSnapshot(
        student_id="ARI2026",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 10, 1, 14, 30),
        courses=[
            # MATH 252 is GONE — dropped
            EnrolledCourse(course_id="CS 310", title="Data Structures",
                           units=3.0, modality=Modality.RESIDENTIAL,
                           status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="PHYS 195", title="Physics I",
                           units=3.0, modality=Modality.DISTANCE,
                           status=CourseEnrollmentStatus.ENROLLED),
            EnrolledCourse(course_id="ENGR 100", title="Intro to Engineering",
                           units=3.0, modality=Modality.DISTANCE,
                           status=CourseEnrollmentStatus.ENROLLED),
        ],
        last_certified=original_cert,
    )

    changes = detect_changes(old_snapshot, new_snapshot)
    amendments = []
    for ch in changes:
        if ch.requires_amendment:
            amendment = generate_amendment(ch, old_snapshot, new_snapshot, original_student)
            if amendment:
                amendments.append(amendment)

    print("\n  REGRESSION CHECK:")
    check("Original certifiable units", original_cert.total_certifiable_units, 13.0)
    check("Original training time", original_cert.training_time, TrainingTime.FULL_TIME)
    check("Number of changes", len(changes), 1)
    if changes:
        check("Change type", changes[0].change_type, ChangeType.COURSE_DROPPED)
        check("Changed course", changes[0].course_id, "MATH 252")
    check("Number of amendments", len(amendments), 1)
    if amendments:
        a = amendments[0]
        check("Revised certifiable units", a.revised_certification.total_certifiable_units, 9.0)
        check("Revised training time", a.revised_certification.training_time, TrainingTime.THREE_QUARTER)
        # Oct 1 > add/drop deadline (Sept 4) → WITHDREW_POST_DROP_NONPUN
        check("Amendment reason", a.reason, AmendmentReason.WITHDREW_POST_DROP_NONPUN)
        # KEY CHECK: post-census (Oct 1 > Sept 21) → HITL required
        check("HITL required (post-census drop)", a.hitl_required, True)
        check("Delta changed course", a.delta['changed_course_id'], "MATH 252")

    print(f"\n    {checks_passed}/{checks_total} checks passed.")
    passed = checks_passed == checks_total
    if passed:
        print("\n    *** POST-CENSUS DROP TEST: ALL CHECKS PASSED ***\n")
    else:
        print(f"\n    *** POST-CENSUS DROP TEST: {checks_total - checks_passed} FAILURES ***\n")
    return passed


# ---------------------------------------------------------------------------
# Test 7: Program Change — requires WEAMS re-match
# ---------------------------------------------------------------------------

def program_change_test():
    """
    Test: Student changes their program/major between snapshots.

    Scenario (SDSU Fall 2026):
      - Ethan Moore originally certified with 12 units in "B.A. Journalism"
      - During the term, he changes to "B.S. Computer Science"
      - Change detection: PROGRAM_CHANGED
      - Re-certification runs with the new program and must re-match WEAMS
      - HITL required: YES (SCO must verify the new program is VA-approved)
      - Amendment reason: OTHER (no standard EM reason covers program changes;
        SCO selects appropriate reason at HITL review)

    This tests WEAMS re-match logic and HITL escalation for program changes.
    """

    from decision_tree import GradingBasis, AcademicLevel

    print("\n" + "=" * 70)
    print("  PROGRAM CHANGE TEST")
    print("  (Major change: B.A. Journalism → B.S. Computer Science)")
    print("=" * 70)

    # Ethan Moore originally in Journalism program
    original_student = StudentInput(
        name="Ethan Moore",
        student_id="EM-007",
        program="B.A. Journalism",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11910105",
        courses=[
            CourseSchedule(
                course_id="JOUR 301",
                title="Reporting and Writing",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="JOUR 350",
                title="Digital Media Production",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="CS 310",
                title="Data Structures",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="elective",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="CS 320",
                title="Algorithms",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="elective",
                has_in_person_session=True,
                all_online=False,
            ),
        ],
    )

    original_cert = run_decision_tree(original_student)

    # Original snapshot: certified Aug 25, 2026 with Journalism major
    old_snapshot = EnrollmentSnapshot(
        student_id="EM-007",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 8, 25, 10, 0, 0),
        program="B.A. Journalism",  # Original program
        courses=[
            EnrolledCourse(
                course_id="JOUR 301",
                title="Reporting and Writing",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="JOUR 350",
                title="Digital Media Production",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="CS 310",
                title="Data Structures",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="CS 320",
                title="Algorithms",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
        ],
        last_certified=original_cert,
    )

    # New snapshot: Sept 10 — student changed program to B.S. Computer Science
    new_snapshot = EnrollmentSnapshot(
        student_id="EM-007",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 9, 10, 14, 0, 0),
        program="B.S. Computer Science",  # NEW PROGRAM
        courses=[
            EnrolledCourse(
                course_id="JOUR 301",
                title="Reporting and Writing",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="JOUR 350",
                title="Digital Media Production",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="CS 310",
                title="Data Structures",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="CS 320",
                title="Algorithms",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
        ],
        last_certified=original_cert,
    )

    changes = detect_changes(old_snapshot, new_snapshot)
    amendments = []
    for change in changes:
        amendment = generate_amendment(change, old_snapshot, new_snapshot, original_student)
        if amendment:
            amendments.append(amendment)

    print("\n  REGRESSION CHECK:")
    checks_passed = 0
    checks_total = 0

    def check(description, actual, expected):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            checks_passed += 1
        print(f"    [{status}] {description}: expected={expected}, got={actual}")

    check("Original certifiable units", original_cert.total_certifiable_units, 12.0)
    check("Original training time", original_cert.training_time, TrainingTime.FULL_TIME)
    check("Number of changes detected", len(changes), 1)
    if changes:
        check("Change type", changes[0].change_type, ChangeType.PROGRAM_CHANGED)
        check("Old program", changes[0].old_value, "B.A. Journalism")
        check("New program", changes[0].new_value, "B.S. Computer Science")
        check("Requires amendment", changes[0].requires_amendment, True)
    check("Number of amendments", len(amendments), 1)
    if amendments:
        a = amendments[0]
        # Revised certification uses the new program
        check("Revised program in certification", a.revised_certification.program, "B.S. Computer Science")
        # Same units, so training time unchanged
        check("Revised certifiable units", a.revised_certification.total_certifiable_units, 12.0)
        check("Revised training time", a.revised_certification.training_time, TrainingTime.FULL_TIME)
        # Amendment reason for program change: OTHER (SCO selects specific reason at HITL review)
        check("Amendment reason", a.reason, AmendmentReason.OTHER)
        # HITL REQUIRED: SCO must verify new program is VA-approved
        check("HITL required (program change)", a.hitl_required, True)
        # Delta includes program fields
        check("Delta has original_program", "original_program" in a.delta, True)
        check("Delta has revised_program", "revised_program" in a.delta, True)

    print(f"\n    {checks_passed}/{checks_total} checks passed.")
    passed = checks_passed == checks_total
    if passed:
        print("\n    *** PROGRAM CHANGE TEST: ALL CHECKS PASSED ***\n")
    else:
        print(f"\n    *** PROGRAM CHANGE TEST: {checks_total - checks_passed} FAILURES ***\n")
    return passed


# ---------------------------------------------------------------------------
# Test 8: Graduation — degree conferred
# ---------------------------------------------------------------------------

def graduation_test():
    """
    Test: Student's degree is conferred (graduation).

    Scenario (SDSU Fall 2026):
      - Isabella Chen certified with 9 units in "M.C.P. City Planning"
      - On Dec 15 (after last day of classes), degree is conferred
      - Change detection: GRADUATION
      - Amendment reason: OTHER (graduation uses the EM Graduation CHECKBOX, not the reason dropdown)
      - HITL required: YES (SCO must verify degree conferral date and grades posted)
      - Amendment includes graduation_date in delta

    This tests graduation handling and final-term certification.
    """

    from decision_tree import GradingBasis, AcademicLevel

    print("\n" + "=" * 70)
    print("  GRADUATION TEST")
    print("  (Degree conferral: M.C.P. City Planning)")
    print("=" * 70)

    # Isabella Chen: graduate student in City Planning
    original_student = StudentInput(
        name="Isabella Chen",
        student_id="IC-008",
        program="M.C.P. City Planning",
        academic_level=AcademicLevel.MASTERS,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11910105",
        courses=[
            CourseSchedule(
                course_id="CP 501",
                title="Urban Planning Theory",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="CP 520",
                title="Planning Methods",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="CP 695",
                title="Masters Project",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=False,
                all_online=True,
            ),
        ],
    )

    original_cert = run_decision_tree(original_student)

    # Certified Aug 25, 2026
    old_snapshot = EnrollmentSnapshot(
        student_id="IC-008",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 8, 25, 10, 0, 0),
        program="M.C.P. City Planning",
        graduated=False,  # Not yet graduated
        courses=[
            EnrolledCourse(
                course_id="CP 501",
                title="Urban Planning Theory",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="CP 520",
                title="Planning Methods",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="CP 695",
                title="Masters Project",
                units=3.0,
                modality=Modality.DISTANCE,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
        ],
        last_certified=original_cert,
    )

    # Dec 15 snapshot: degree conferred
    new_snapshot = EnrollmentSnapshot(
        student_id="IC-008",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 12, 15, 16, 30, 0),
        program="M.C.P. City Planning",
        graduated=True,  # DEGREE CONFERRED
        courses=[
            EnrolledCourse(
                course_id="CP 501",
                title="Urban Planning Theory",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="CP 520",
                title="Planning Methods",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="CP 695",
                title="Masters Project",
                units=3.0,
                modality=Modality.DISTANCE,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
        ],
        last_certified=original_cert,
    )

    changes = detect_changes(old_snapshot, new_snapshot)
    amendments = []
    for change in changes:
        amendment = generate_amendment(change, old_snapshot, new_snapshot, original_student)
        if amendment:
            amendments.append(amendment)

    print("\n  REGRESSION CHECK:")
    checks_passed = 0
    checks_total = 0

    def check(description, actual, expected):
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "PASS" if actual == expected else "FAIL"
        if status == "PASS":
            checks_passed += 1
        print(f"    [{status}] {description}: expected={expected}, got={actual}")

    check("Original certifiable units", original_cert.total_certifiable_units, 9.0)
    check("Original training time", original_cert.training_time, TrainingTime.FULL_TIME)
    check("Number of changes detected", len(changes), 1)
    if changes:
        check("Change type", changes[0].change_type, ChangeType.GRADUATION)
        check("Old value", changes[0].old_value, "not_graduated")
        check("New value", changes[0].new_value, "graduated")
        check("Requires amendment", changes[0].requires_amendment, True)
    check("Number of amendments", len(amendments), 1)
    if amendments:
        a = amendments[0]
        # Revised certification maintains student's enrollment
        check("Revised certifiable units", a.revised_certification.total_certifiable_units, 9.0)
        check("Revised training time", a.revised_certification.training_time, TrainingTime.FULL_TIME)
        # Amendment reason for graduation: OTHER (graduation is a EM checkbox, not a dropdown reason)
        check("Amendment reason", a.reason, AmendmentReason.OTHER)
        # HITL REQUIRED: SCO must verify degree conferral and grades posted
        check("HITL required (graduation)", a.hitl_required, True)
        # Delta includes graduation_date
        check("Delta has graduation_date", "graduation_date" in a.delta, True)
        if "graduation_date" in a.delta:
            check(
                "Graduation date value",
                a.delta["graduation_date"],
                "2026-12-15",
            )

    print(f"\n    {checks_passed}/{checks_total} checks passed.")
    passed = checks_passed == checks_total
    if passed:
        print("\n    *** GRADUATION TEST: ALL CHECKS PASSED ***\n")
    else:
        print(f"\n    *** GRADUATION TEST: {checks_total - checks_passed} FAILURES ***\n")
    return passed


# ---------------------------------------------------------------------------
# Test Harness
# ---------------------------------------------------------------------------

def run_all_tests():
    """Run all regression tests for enrollment_monitor.py."""

    print("\n" + "=" * 70)
    print("  ENROLLMENT MONITOR — PHASE 3 TEST SUITE (EXPANDED)")
    print(f"  SDSU Fall 2026 Academic Calendar:")
    print(f"    Instruction begins:  {SDSU_FALL_2026['instruction_begins']}")
    print(f"    Add/drop deadline:   {SDSU_FALL_2026['add_drop_deadline']}")
    print(f"    Census date:         {SDSU_FALL_2026['census_date']}")
    print(f"    Withdrawal deadline: {SDSU_FALL_2026['withdrawal_deadline']}")
    print("=" * 70)

    test_results = []

    # Test 1: James Roster — course drop before add/drop deadline
    result = james_roster_amendment_test()
    test_results.append(("1. James Roster: Course Drop (before add/drop)", result))

    # Test 2: Withdrawal after add/drop deadline
    result = withdrawal_after_deadline_test()
    test_results.append(("2. Sarah Kim: Withdrawal (after add/drop)", result))

    # Test 3: Course add — no amendment
    result = course_add_no_amendment_test()
    test_results.append(("3. Daniel Bahena: Course Add (no amendment)", result))

    # Test 4: Never attended — all courses dropped
    result = never_attended_test()
    test_results.append(("4. James Chen: Never Attended (all dropped)", result))

    # Test 5: Unit change on existing course
    result = unit_change_test()
    test_results.append(("5. Robert Torres: Unit Change (4→3 units)", result))

    # Test 6: Post-census drop — HITL required due to overpayment risk
    result = post_census_drop_test()
    test_results.append(("6. Alex Rivera: Post-Census Drop (HITL escalation)", result))

    # Test 7: Program change — WEAMS re-match with HITL escalation
    result = program_change_test()
    test_results.append(("7. Ethan Moore: Program Change (WEAMS re-match)", result))

    # Test 8: Graduation — degree conferred
    result = graduation_test()
    test_results.append(("8. Isabella Chen: Graduation (degree conferred)", result))

    # Summary
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)
    for test_name, passed in test_results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {test_name}")

    all_passed = all(result for _, result in test_results)
    total = len(test_results)
    passed_count = sum(1 for _, result in test_results if result)

    total_checks = 20 + 10 + 5 + 8 + 13 + 11 + 11 + 12  # Sum of all individual checks
    print(f"\n  {passed_count}/{total} test suites passed")
    print(f"  {total_checks} total regression checks")

    if all_passed:
        print("\n  *** ALL TESTS PASSED ***\n")
    else:
        print(f"\n  *** {total - passed_count} TEST SUITE(S) FAILED ***\n")

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
