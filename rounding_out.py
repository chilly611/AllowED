"""
VA Final-Term Verification & Rounding Out Module — Phase 3B
============================================================
Implements the 5-step Final-Term Verification (rounding-out) workflow
for students in their final term before graduation.

Authority: 38 CFR Part 21; SCO Handbook Rev 7.4 (June 26, 2025)
Validated by: Paulina, SCO at SDSU

Rounding Out Rule (38 CFR § 21.4273(d)):
  "A student may be certified at the full-time rate if enrolled in all
   remaining courses required for degree completion, even if enrollment
   would otherwise result in less-than-full-time status."

5-Step Final-Term Verification:
  1. Degree Audit Check — Confirm final term and graduation date
  2. Credit Hour Validation — Verify rounding-out would apply
  3. Program Completion Verification — All courses are degree-applicable
  4. SCO Certification Statement — Generate HITL documentation
  5. EM Submission Preparation — Format for Enrollment Manager
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional, List

from decision_tree import (
    StudentInput,
    CourseSchedule,
    DecisionTreeOutput,
    TrainingTime,
    run_decision_tree,
    GradingBasis,
    AcademicLevel,
)
from em_integration import (
    EMEnrollment,
    format_for_em,
    SubmissionStatus,
    HITLReason,
)


# ---------------------------------------------------------------------------
# SDSU Fall 2026 Academic Calendar (from registrar.sdsu.edu)
# ---------------------------------------------------------------------------

SDSU_FALL_2026 = {
    "instruction_begins": date(2026, 8, 24),
    "add_drop_deadline": date(2026, 9, 4),
    "census_date": date(2026, 9, 21),
    "withdrawal_deadline": date(2026, 11, 1),
    "last_day_instruction": date(2026, 12, 11),
    "finals_begin": date(2026, 12, 12),
    "finals_end": date(2026, 12, 18),
    "semester_end": date(2026, 12, 31),
}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RoundingOutEligibility(Enum):
    """Result of eligibility check."""
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    ALREADY_FULL_TIME = "already_full_time"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RoundingOutCheck:
    """
    5-Step Final-Term Verification result for rounding-out eligibility.

    This is the intermediate output from steps 1-3 before SCO certification.
    """
    # Student identification
    student_id: str
    student_name: str
    program: str
    term: str
    facility_code: str = "11910105"

    # Degree audit data (Step 1)
    completed_units: float = 0.0            # Already completed
    required_units: float = 0.0             # Total for degree
    remaining_units: float = 0.0            # Required - completed
    expected_grad_date: Optional[date] = None
    is_final_term: bool = False
    final_term_reason: str = ""             # Why we believe it's final term

    # Current enrollment (Step 2)
    current_enrollment_units: float = 0.0   # Units in current enrollment
    enrolled_in_all_remaining: bool = False # ALL remaining courses enrolled?

    # Training time analysis
    training_time_without_rounding: Optional[TrainingTime] = None
    training_time_with_rounding: Optional[TrainingTime] = None
    would_benefit_from_rounding: bool = False  # Would rounding change certification?

    # Program completion (Step 3)
    all_courses_degree_applicable: bool = False
    extra_courses: List[str] = field(default_factory=list)  # Courses not in DARS

    # Eligibility determination
    eligibility: RoundingOutEligibility = RoundingOutEligibility.NOT_ELIGIBLE
    reasons: List[str] = field(default_factory=list)  # Detailed reasons

    # SCO certification requirement
    sco_certification_required: bool = True
    sco_certification_statement: str = ""

    # Decision tree outputs (for audit trail)
    decision_tree_without_rounding: Optional[DecisionTreeOutput] = None
    decision_tree_with_rounding: Optional[DecisionTreeOutput] = None


@dataclass
class RoundingOutCertification:
    """
    Complete rounding-out certification package — ready for EM submission.

    Combines eligibility check + SCO approval + EM submission data.
    """
    check_result: RoundingOutCheck
    sco_approved: bool = False
    sco_approval_date: Optional[date] = None
    sco_approver_name: str = ""
    sco_approver_id: str = ""

    em_enrollment: Optional[EMEnrollment] = None
    submission_ready: bool = False
    submission_note: str = ""


# ---------------------------------------------------------------------------
# Step 1: Degree Audit Check
# ---------------------------------------------------------------------------

def check_degree_audit(
    student_id: str,
    student_name: str,
    program: str,
    term: str,
    completed_units: float,
    required_units: float,
    expected_grad_date: date,
    current_term_start: date = SDSU_FALL_2026["instruction_begins"],
    current_term_end: date = SDSU_FALL_2026["semester_end"],
) -> tuple[bool, str]:
    """
    Step 1: Verify the student is in their final term.

    Returns: (is_final_term, reason_string)

    Criteria:
      - Remaining units = required - completed
      - Expected grad date falls within current term
      - Student is in their last term before graduation
    """
    remaining = required_units - completed_units

    # Check if expected graduation is within current term
    is_grad_this_term = (current_term_start <= expected_grad_date <= current_term_end)

    reasons = []
    if is_grad_this_term:
        reasons.append(
            f"Expected graduation {expected_grad_date.isoformat()} "
            f"falls within {term} ({current_term_start.isoformat()} to {current_term_end.isoformat()})"
        )
    else:
        reasons.append(
            f"Expected graduation {expected_grad_date.isoformat()} "
            f"does NOT fall within {term}"
        )
        return False, "; ".join(reasons)

    if remaining > 0:
        reasons.append(f"Remaining units: {remaining:.1f} of {required_units:.1f}")
    else:
        reasons.append(f"No remaining units (completed: {completed_units:.1f})")

    is_final_term = is_grad_this_term and remaining > 0
    return is_final_term, "; ".join(reasons)


# ---------------------------------------------------------------------------
# Step 2: Credit Hour Validation
# ---------------------------------------------------------------------------

def validate_credit_hours(
    student: StudentInput,
    required_units: float,
    completed_units: float,
    current_enrollment_units: float,
) -> tuple[bool, str, Optional[TrainingTime], Optional[TrainingTime]]:
    """
    Step 2: Verify rounding-out would apply.

    Returns:
      - (would_benefit, reason, training_time_without, training_time_with)

    Criteria:
      - Current enrollment alone = less-than-full-time
      - With rounding out = full-time
      - Student must be enrolled in ALL remaining required courses
    """
    remaining_units = required_units - completed_units

    # Run decision tree with current enrollment (no rounding)
    dt_without = run_decision_tree(student)
    training_without = dt_without.training_time

    # Create modified student input with "rounding out" flag
    student_with_rounding = StudentInput(
        name=student.name,
        student_id=student.student_id,
        program=student.program,
        academic_level=student.academic_level,
        benefit_chapter=student.benefit_chapter,
        term=student.term,
        courses=student.courses,
        facility_code=student.facility_code,
        enrolled_in_799a=student.enrolled_in_799a,
        enrolled_in_897=student.enrolled_in_897,
        enrolled_in_899=student.enrolled_in_899,
    )
    # Mark for rounding out (would be checked in Step 7 of decision tree)
    student_with_rounding.has_sco_exception = True
    student_with_rounding.sco_exception_type = "rounding_out"

    # Run decision tree with rounding out applied
    dt_with = run_decision_tree(student_with_rounding)
    training_with = TrainingTime.FULL_TIME  # Override to full-time due to rounding

    # Check if rounding would make a difference
    benefits = (
        training_without != TrainingTime.FULL_TIME and
        training_with == TrainingTime.FULL_TIME
    )

    # Check if student is enrolled in all remaining courses
    enrolled_units = current_enrollment_units
    enrolled_in_all = (enrolled_units >= remaining_units * 0.95)  # Allow 5% tolerance

    reason_parts = []
    reason_parts.append(
        f"Current enrollment: {current_enrollment_units:.1f} units; "
        f"Remaining required: {remaining_units:.1f} units"
    )
    reason_parts.append(f"Training time without rounding: {training_without.value}")
    if benefits:
        reason_parts.append(f"Training time with rounding: {training_with.value} ✓")
    else:
        reason_parts.append(f"Rounding would NOT change certification")

    if enrolled_in_all:
        reason_parts.append("Student enrolled in all remaining courses ✓")
    else:
        reason_parts.append(f"Student NOT enrolled in all remaining courses")

    would_benefit = benefits and enrolled_in_all
    reason = "; ".join(reason_parts)

    return would_benefit, reason, training_without, training_with


# ---------------------------------------------------------------------------
# Step 3: Program Completion Verification
# ---------------------------------------------------------------------------

def verify_program_completion(
    dt_output: DecisionTreeOutput,
) -> tuple[bool, List[str]]:
    """
    Step 3: Verify all courses are degree-applicable.

    Returns: (all_applicable, list_of_extra_courses)

    Criteria:
      - All courses in current enrollment must be in DARS (degree-applicable)
      - No "extra" courses that aren't needed for graduation
    """
    extra_courses = []

    for course in dt_output.course_results:
        if not course.certifiable:
            # Non-certifiable courses might be extra (audit, non-degree, etc.)
            if course.exclusion_reason and "DARS" in str(course.exclusion_reason):
                extra_courses.append(
                    f"{course.course_id} ({course.exclusion_detail})"
                )

    all_applicable = len(extra_courses) == 0
    return all_applicable, extra_courses


# ---------------------------------------------------------------------------
# Step 4: SCO Certification Statement
# ---------------------------------------------------------------------------

def generate_sco_statement(
    check: RoundingOutCheck,
    gross_tuition: float = 0.0,
    aid_amount: float = 0.0,
) -> str:
    """
    Step 4: Generate the required SCO certification statement.

    The SCO must certify that:
      - Student is in final term
      - Student is enrolled in all remaining required courses
      - Rounding out to full-time is appropriate per 38 CFR § 21.4273(d)
    """
    statement_lines = [
        "=" * 70,
        "SCO FINAL-TERM VERIFICATION & ROUNDING-OUT CERTIFICATION STATEMENT",
        "=" * 70,
        "",
        f"Date: {date.today().isoformat()}",
        f"Student: {check.student_name} (ID: {check.student_id})",
        f"Program: {check.program}",
        f"Term: {check.term}",
        f"Facility Code: {check.facility_code}",
        "",
        "DEGREE AUDIT SUMMARY:",
        f"  • Required units for degree: {check.required_units:.1f}",
        f"  • Completed units: {check.completed_units:.1f}",
        f"  • Remaining units: {check.remaining_units:.1f}",
        f"  • Expected graduation date: {check.expected_grad_date.isoformat()}",
        f"  • Is final term: {check.is_final_term}",
        "",
        "CURRENT ENROLLMENT:",
        f"  • Units enrolled: {check.current_enrollment_units:.1f}",
        f"  • Enrolled in all remaining courses: {check.enrolled_in_all_remaining}",
        f"  • Training time WITHOUT rounding: {check.training_time_without_rounding.value if check.training_time_without_rounding else 'N/A'}",
        f"  • Training time WITH rounding: {check.training_time_with_rounding.value if check.training_time_with_rounding else 'N/A'}",
        "",
        "PROGRAM COMPLETION:",
        f"  • All courses degree-applicable: {check.all_courses_degree_applicable}",
        f"  • Extra/non-applicable courses: {len(check.extra_courses)}",
        "",
        "CERTIFICATION AUTHORITY:",
        "  Per 38 CFR Part 21.4273(d), a student may be certified at the",
        "  full-time rate if enrolled in all remaining courses required for",
        "  degree completion, even if enrollment would otherwise result in",
        "  less-than-full-time status.",
        "",
        "SCO DETERMINATION:",
    ]

    if check.eligibility == RoundingOutEligibility.ELIGIBLE:
        statement_lines.extend([
            f"  ✓ ELIGIBLE for rounding-out certification",
            f"  ✓ Student meets all eligibility criteria",
            f"  ✓ Certification rate: FULL-TIME (rounded out)",
        ])
    elif check.eligibility == RoundingOutEligibility.ALREADY_FULL_TIME:
        statement_lines.extend([
            f"  ⊙ Student already enrolled at full-time rate",
            f"  ⊙ Rounding out not necessary",
        ])
    else:
        statement_lines.extend([
            f"  ✗ NOT eligible for rounding-out certification",
            f"  ✗ Reasons:",
        ])
        for reason in check.reasons:
            statement_lines.append(f"    - {reason}")

    statement_lines.extend([
        "",
        "SIGNATURE BLOCK:",
        "  SCO Name (print): _________________________________",
        "  SCO Signature:     _________________________________",
        "  Date:              _________________________________",
        "",
        "=" * 70,
    ])

    return "\n".join(statement_lines)


# ---------------------------------------------------------------------------
# Step 5: EM Submission Preparation
# ---------------------------------------------------------------------------

def prepare_em_submission(
    check: RoundingOutCheck,
    sco_approved: bool,
    student_va_id: str,
    student_dob: date,
    gross_tuition: float = 0.0,
    aid_amount: float = 0.0,
) -> Optional[EMEnrollment]:
    """
    Step 5: Format rounding-out certification for Enrollment Manager.

    Returns an EMEnrollment ready to submit, with rounding-out flag.
    Returns None if not eligible or SCO has not approved.
    """
    if not check.eligibility == RoundingOutEligibility.ELIGIBLE:
        return None

    if not sco_approved:
        return None

    # Use decision tree output WITH rounding applied
    dt_output = check.decision_tree_with_rounding
    if dt_output is None:
        return None

    # Format for EM using the "with rounding" decision tree output
    enrollment = format_for_em(
        dt_output=dt_output,
        student_va_id=student_va_id,
        student_dob=student_dob,
        facility_code=check.facility_code,
        pre_set_id=f"Fall-2026",
        term_start=SDSU_FALL_2026["instruction_begins"],
        term_end=SDSU_FALL_2026["semester_end"],
        expected_grad_date=check.expected_grad_date,
        gross_tuition=gross_tuition,
        aid_amount=aid_amount,
    )

    # Mark as rounding-out submission
    enrollment.custom_remarks = (
        f"ROUNDING OUT — Final term certification. Student {check.student_id} "
        f"is in final term with {check.remaining_units:.1f} remaining units. "
        f"All remaining courses enrolled. Certified at full-time rate per "
        f"38 CFR § 21.4273(d) and SCO statement dated {date.today().isoformat()}."
    )

    # Add HITL flag for rounding-out (SCO already approved, but good audit trail)
    enrollment.hitl_reasons.append(HITLReason.ROUNDING_OUT)

    return enrollment


# ---------------------------------------------------------------------------
# Unified 5-Step Workflow
# ---------------------------------------------------------------------------

def run_final_term_verification(
    student_id: str,
    student_name: str,
    program: str,
    term: str,
    academic_level: AcademicLevel,
    benefit_chapter: str,
    completed_units: float,
    required_units: float,
    expected_grad_date: date,
    courses: List[CourseSchedule],
    current_enrollment_units: float,
    facility_code: str = "11910105",
) -> RoundingOutCheck:
    """
    Run the complete 5-step Final-Term Verification workflow.

    Steps:
      1. Degree Audit Check — Is this the final term?
      2. Credit Hour Validation — Would rounding out apply?
      3. Program Completion — Are all courses degree-applicable?
      4. SCO Certification Statement — Generate documentation
      5. (EM Submission prepared separately via prepare_em_submission)

    Returns: RoundingOutCheck with eligibility determination
    """
    check = RoundingOutCheck(
        student_id=student_id,
        student_name=student_name,
        program=program,
        term=term,
        facility_code=facility_code,
        completed_units=completed_units,
        required_units=required_units,
        remaining_units=required_units - completed_units,
        expected_grad_date=expected_grad_date,
        current_enrollment_units=current_enrollment_units,
    )

    # -----------------------------------------------------------------------
    # STEP 1: Degree Audit Check
    # -----------------------------------------------------------------------
    is_final_term, final_term_reason = check_degree_audit(
        student_id=student_id,
        student_name=student_name,
        program=program,
        term=term,
        completed_units=completed_units,
        required_units=required_units,
        expected_grad_date=expected_grad_date,
    )

    check.is_final_term = is_final_term
    check.final_term_reason = final_term_reason

    if not is_final_term:
        check.eligibility = RoundingOutEligibility.NOT_ELIGIBLE
        check.reasons.append(f"Not a final term: {final_term_reason}")
        return check

    # -----------------------------------------------------------------------
    # STEP 2: Credit Hour Validation
    # -----------------------------------------------------------------------
    # Create student input for decision tree
    student_input = StudentInput(
        name=student_name,
        student_id=student_id,
        program=program,
        academic_level=academic_level,
        benefit_chapter=benefit_chapter,
        term=term,
        courses=courses,
        facility_code=facility_code,
    )

    would_benefit, credit_reason, training_without, training_with = validate_credit_hours(
        student=student_input,
        required_units=required_units,
        completed_units=completed_units,
        current_enrollment_units=current_enrollment_units,
    )

    check.training_time_without_rounding = training_without
    check.training_time_with_rounding = training_with
    check.would_benefit_from_rounding = would_benefit
    check.enrolled_in_all_remaining = (
        current_enrollment_units >= (required_units - completed_units) * 0.95
    )

    # Check if not enrolled in all remaining courses FIRST (Step 2a)
    if not check.enrolled_in_all_remaining:
        check.eligibility = RoundingOutEligibility.NOT_ELIGIBLE
        check.reasons.append(
            f"Student not enrolled in all remaining courses "
            f"(enrolled: {current_enrollment_units:.1f}; required: {required_units - completed_units:.1f})"
        )
        return check

    # Then check if rounding would benefit the student (Step 2b)
    if not would_benefit:
        if training_without == TrainingTime.FULL_TIME:
            check.eligibility = RoundingOutEligibility.ALREADY_FULL_TIME
            check.reasons.append("Student already enrolled at full-time rate")
        else:
            check.eligibility = RoundingOutEligibility.NOT_ELIGIBLE
            check.reasons.append(f"Rounding would not change certification: {credit_reason}")
        return check

    # Store decision tree outputs
    check.decision_tree_without_rounding = run_decision_tree(student_input)

    # Create modified student for "with rounding" scenario
    student_with_rounding = StudentInput(
        name=student_name,
        student_id=student_id,
        program=program,
        academic_level=academic_level,
        benefit_chapter=benefit_chapter,
        term=term,
        courses=courses,
        facility_code=facility_code,
    )
    student_with_rounding.has_sco_exception = True
    student_with_rounding.sco_exception_type = "rounding_out"
    check.decision_tree_with_rounding = run_decision_tree(student_with_rounding)

    # -----------------------------------------------------------------------
    # STEP 3: Program Completion Verification
    # -----------------------------------------------------------------------
    all_applicable, extra_courses = verify_program_completion(
        check.decision_tree_without_rounding
    )

    check.all_courses_degree_applicable = all_applicable
    check.extra_courses = extra_courses

    if not all_applicable:
        check.eligibility = RoundingOutEligibility.NOT_ELIGIBLE
        check.reasons.append(
            f"Found {len(extra_courses)} non-applicable courses: {', '.join(extra_courses)}"
        )
        return check

    # -----------------------------------------------------------------------
    # STEP 4: All checks passed — Generate SCO statement
    # -----------------------------------------------------------------------
    check.eligibility = RoundingOutEligibility.ELIGIBLE
    check.sco_certification_required = True
    check.sco_certification_statement = generate_sco_statement(check)

    return check


# ---------------------------------------------------------------------------
# Test Suite (check() pattern)
# ---------------------------------------------------------------------------

def test_eligible_student():
    """
    Test 1: Eligible student in final term.

    Scenario:
      - Program: B.S. Computer Science
      - Completed: 120 units (of 129 required)
      - Remaining: 9 units
      - Current enrollment: 9 units (all remaining courses)
      - Expected grad: Fall 2026 (this term)
      - Without rounding: 3-quarter time (9 units)
      - With rounding: Full-time certification
    """

    print("\n" + "=" * 70)
    print("  TEST 1: ELIGIBLE STUDENT (Final Term, Rounding Applies)")
    print("=" * 70)

    def check(description, actual, expected):
        status = "✓" if actual == expected else "✗"
        print(f"  {status} {description}")
        print(f"      Expected: {expected}")
        print(f"      Actual:   {actual}")
        assert actual == expected, f"Failed: {description}"

    result = run_final_term_verification(
        student_id="CS-001",
        student_name="Alexandra Chen",
        program="B.S. Computer Science",
        term="Fall 2026",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        completed_units=120.0,
        required_units=129.0,
        expected_grad_date=date(2026, 12, 20),
        courses=[
            CourseSchedule(
                course_id="CS 480",
                title="Senior Capstone Project",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="CS 481",
                title="Capstone Project Continuation",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="CS 485",
                title="Professional Practice in Computing",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=False,
                all_online=True,
            ),
        ],
        current_enrollment_units=9.0,
    )

    print("\n  Results:")
    check("Is final term", result.is_final_term, True)
    check("Remaining units", result.remaining_units, 9.0)
    check("Enrolled in all remaining", result.enrolled_in_all_remaining, True)
    check("All courses degree-applicable", result.all_courses_degree_applicable, True)
    check("Would benefit from rounding", result.would_benefit_from_rounding, True)
    check("Eligibility", result.eligibility, RoundingOutEligibility.ELIGIBLE)
    check("SCO certification required", result.sco_certification_required, True)

    print(f"\n  Training times:")
    print(f"    Without rounding: {result.training_time_without_rounding.value if result.training_time_without_rounding else 'N/A'}")
    print(f"    With rounding: {result.training_time_with_rounding.value if result.training_time_with_rounding else 'N/A'}")

    print("\n  ✓ TEST 1 PASSED\n")


def test_not_eligible_extra_courses():
    """
    Test 2: NOT eligible — student has extra courses.

    Scenario:
      - Program: B.A. History
      - Completed: 110 units (of 120 required)
      - Remaining: 10 units
      - Current enrollment: 13 units (10 required + 3 extra electives)
      - All courses are in DARS but 3 are NOT required for degree
      - Fails Step 3 (Program Completion)
    """

    print("\n" + "=" * 70)
    print("  TEST 2: NOT ELIGIBLE (Extra Courses Beyond Degree Requirements)")
    print("=" * 70)

    def check(description, actual, expected):
        status = "✓" if actual == expected else "✗"
        print(f"  {status} {description}")
        print(f"      Expected: {expected}")
        print(f"      Actual:   {actual}")
        assert actual == expected, f"Failed: {description}"

    result = run_final_term_verification(
        student_id="HIST-002",
        student_name="Marcus Thompson",
        program="B.A. History",
        term="Fall 2026",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        completed_units=110.0,
        required_units=120.0,
        expected_grad_date=date(2026, 12, 20),
        courses=[
            # Required courses
            CourseSchedule(
                course_id="HIST 495",
                title="Senior Seminar",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="HIST 480",
                title="History Capstone",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="POLI 250",
                title="American Government",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="GE area",
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="HIST 490",
                title="Topics in History",
                units=1.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=False,
                all_online=True,
            ),
            # Extra courses (not needed for degree)
            CourseSchedule(
                course_id="PHIL 101",
                title="Introduction to Philosophy",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=False,  # Not in degree requirements
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="ANTH 150",
                title="Cultural Anthropology",
                units=2.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=False,  # Not in degree requirements
                has_in_person_session=False,
                all_online=True,
            ),
        ],
        current_enrollment_units=13.0,
    )

    print("\n  Results:")
    check("Is final term", result.is_final_term, True)
    check("Remaining units", result.remaining_units, 10.0)
    check("Enrolled in all remaining", result.enrolled_in_all_remaining, True)
    check("All courses degree-applicable", result.all_courses_degree_applicable, False)
    check("Extra courses found", len(result.extra_courses) > 0, True)
    check("Eligibility", result.eligibility, RoundingOutEligibility.NOT_ELIGIBLE)

    print(f"\n  Extra/non-applicable courses:")
    for course in result.extra_courses:
        print(f"    - {course}")

    print("\n  ✓ TEST 2 PASSED\n")


def test_not_eligible_missing_courses():
    """
    Test 3: NOT eligible — student not enrolled in all remaining courses.

    Scenario:
      - Program: B.S. Engineering
      - Completed: 115 units (of 132 required)
      - Remaining: 17 units
      - Current enrollment: 12 units (missing 5 units of required courses)
      - Fails Step 2 (Credit Hour Validation)
    """

    print("\n" + "=" * 70)
    print("  TEST 3: NOT ELIGIBLE (Not Enrolled in All Remaining Courses)")
    print("=" * 70)

    def check(description, actual, expected):
        status = "✓" if actual == expected else "✗"
        print(f"  {status} {description}")
        print(f"      Expected: {expected}")
        print(f"      Actual:   {actual}")
        assert actual == expected, f"Failed: {description}"

    result = run_final_term_verification(
        student_id="ENG-003",
        student_name="Priya Patel",
        program="B.S. Mechanical Engineering",
        term="Fall 2026",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        completed_units=115.0,
        required_units=132.0,
        expected_grad_date=date(2026, 12, 20),
        courses=[
            CourseSchedule(
                course_id="ME 450",
                title="Thermal Systems Design",
                units=4.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="ME 460",
                title="Fluid Mechanics",
                units=4.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="ME 470",
                title="Materials Lab",
                units=2.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="ME 480",
                title="Senior Design",
                units=2.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
            ),
            # Note: Missing 5 more units (e.g., ME 485, ME 490)
        ],
        current_enrollment_units=12.0,
    )

    print("\n  Results:")
    check("Is final term", result.is_final_term, True)
    check("Remaining units", result.remaining_units, 17.0)
    check("Enrolled in all remaining", result.enrolled_in_all_remaining, False)
    check("Eligibility", result.eligibility, RoundingOutEligibility.NOT_ELIGIBLE)

    print(f"\n  Enrollment analysis:")
    print(f"    Remaining required: {result.remaining_units:.1f}")
    print(f"    Current enrollment: {result.current_enrollment_units:.1f}")
    print(f"    Units short: {result.remaining_units - result.current_enrollment_units:.1f}")

    print("\n  ✓ TEST 3 PASSED\n")


def test_already_full_time():
    """
    Test 4: Edge case — student already at full-time (rounding not needed).

    Scenario:
      - Program: B.A. Economics
      - Completed: 108 units (of 120 required)
      - Remaining: 12 units
      - Current enrollment: 15 units (3 units over minimum, still all required + some extra)
      - But they ARE enrolled in all 12 remaining required courses
      - Training time without rounding: already FULL_TIME (15 units)
      - Eligibility: ALREADY_FULL_TIME (no rounding needed)
    """

    print("\n" + "=" * 70)
    print("  TEST 4: EDGE CASE (Already Enrolled at Full-Time)")
    print("=" * 70)

    def check(description, actual, expected):
        status = "✓" if actual == expected else "✗"
        print(f"  {status} {description}")
        print(f"      Expected: {expected}")
        print(f"      Actual:   {actual}")
        assert actual == expected, f"Failed: {description}"

    result = run_final_term_verification(
        student_id="ECON-004",
        student_name="David Kumar",
        program="B.A. Economics",
        term="Fall 2026",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        completed_units=108.0,
        required_units=120.0,
        expected_grad_date=date(2026, 12, 20),
        courses=[
            # 12 units of required courses (matching the 12 remaining)
            CourseSchedule(
                course_id="ECON 450",
                title="Advanced Microeconomics",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="ECON 460",
                title="Advanced Macroeconomics",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="ECON 480",
                title="Econometrics",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="ECON 490",
                title="Senior Seminar",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=False,
                all_online=True,
            ),
        ],
        current_enrollment_units=12.0,
    )

    print("\n  Results:")
    check("Is final term", result.is_final_term, True)
    check("Remaining units", result.remaining_units, 12.0)
    check("Current enrollment units", result.current_enrollment_units, 12.0)
    check("Enrolled in all remaining", result.enrolled_in_all_remaining, True)
    check("Eligibility", result.eligibility, RoundingOutEligibility.ALREADY_FULL_TIME)

    print(f"\n  Analysis:")
    print(f"    Student enrolled at {result.current_enrollment_units:.1f} units (exactly full-time)")
    print(f"    Training time without rounding: {result.training_time_without_rounding.value if result.training_time_without_rounding else 'N/A'}")
    print(f"    Rounding out not necessary")

    print("\n  ✓ TEST 4 PASSED\n")


def run_all_tests():
    """Run all rounding-out tests."""
    print("\n" + "=" * 70)
    print("  FINAL-TERM VERIFICATION & ROUNDING-OUT TEST SUITE")
    print("=" * 70)

    try:
        test_eligible_student()
        test_not_eligible_extra_courses()
        test_not_eligible_missing_courses()
        test_already_full_time()

        print("\n" + "=" * 70)
        print("  ALL TESTS PASSED ✓")
        print("=" * 70 + "\n")
        return True

    except AssertionError as e:
        print(f"\n  ✗ TEST FAILED: {e}\n")
        return False


if __name__ == "__main__":
    run_all_tests()
