"""
VA Course Applicability Decision Tree — Rule Engine v0.1
=========================================================
Implements the 7-step per-course decision tree from the spec:
  1. WEAMS Program Match
  2. DARS Applicability Check
  3. Audit Course Check
  4. Repeat Course Check
  5. Remedial/Deficiency Check (+ modality gate)
  6. Modality Classification (Residential vs Distance)
  7. Rate of Pursuit / Training Time

Authority: SCO Handbook Rev 7.4 (June 26, 2025); 38 CFR Part 21
Validated by: Paulina, SCO at SDSU

First test case: James Roster (Daniel Bahena), B.A. Journalism, Ch.33, Fall 2024
Expected output: R:6, D:6, T:12, ENS 331 excluded
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Modality(Enum):
    RESIDENTIAL = "residential"
    DISTANCE = "distance"


class TrainingTime(Enum):
    FULL_TIME = "full_time"
    THREE_QUARTER = "three_quarter"
    HALF_TIME = "half_time"
    LESS_THAN_HALF = "less_than_half"
    QUARTER_OR_LESS = "quarter_or_less"


class GradingBasis(Enum):
    LETTER = "letter"
    CR_NC = "cr_nc"
    AUDIT = "audit"


class CourseExclReason(Enum):
    NOT_IN_WEAMS = "Program not found in WEAMS"
    WEAMS_WITHDRAWN = "Program withdrawn from WEAMS"
    NOT_IN_DARS = "Course not required for degree per DARS"
    AUDIT_COURSE = "Audited courses cannot be certified"
    REPEAT_PASSING = "Repeat of previously passed course — SCO review required"
    REMEDIAL_ONLINE = "Remedial course in online/hybrid format — never certifiable"
    SCO_EXCEPTION = "Routed to SCO exception queue"


class AcademicLevel(Enum):
    UNDERGRADUATE = "undergraduate"
    MASTERS = "masters"
    DOCTORAL = "doctoral"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WEAMSProgram:
    """A single program entry from the WEAMS 1998 report."""
    description: str
    code: str
    effective_start: str          # ISO date
    effective_end: Optional[str]  # None = still active
    active: bool = True


@dataclass
class CourseSchedule:
    """One course on a student's term schedule — input to the Decision Tree."""
    course_id: str           # e.g. "MIS 401"
    title: str               # e.g. "Management Information Systems"
    units: float             # e.g. 3.0
    grading_basis: GradingBasis
    is_remedial: bool = False

    # DARS data
    in_dars: bool = False
    dars_rationale: str = ""  # "major requirement", "GE area", "minor", etc.

    # Modality data  (from PeopleSoft schedule)
    has_in_person_session: bool = False   # at least one REQUIRED 50-min+ in-person
    all_online: bool = False
    is_pre_term_only: bool = False        # in-person meeting is before term starts
    is_practicum: bool = False            # practicum/internship = always residential

    # Repeat data
    previously_passed: bool = False
    repeat_exception: bool = False  # failed, higher grade req, or outdated req

    # SCO exception (advisor approval, rounding out, substitution)
    has_sco_exception: bool = False
    sco_exception_type: str = ""


@dataclass
class CourseResult:
    """Decision Tree output for a single course."""
    course_id: str
    title: str
    units: float
    certifiable: bool
    modality: Optional[Modality] = None
    exclusion_reason: Optional[CourseExclReason] = None
    exclusion_detail: str = ""
    step_failed: Optional[int] = None   # which step excluded the course (1-5)
    flags: list = field(default_factory=list)  # informational flags for SCO


@dataclass
class StudentInput:
    """Everything the Decision Tree needs about a student for one term."""
    name: str
    student_id: str
    program: str              # e.g. "B.A. Journalism"
    academic_level: AcademicLevel
    benefit_chapter: str      # "ch33", "ch35", "ch31"
    term: str                 # e.g. "Fall 2024"
    courses: list             # list of CourseSchedule
    facility_code: str = "11910105"  # VA Facility Code (default: SDSU)

    # Special full-time triggers
    enrolled_in_799a: bool = False   # Thesis
    enrolled_in_897: bool = False    # Doctoral Research
    enrolled_in_899: bool = False    # Dissertation


@dataclass
class DecisionTreeOutput:
    """Complete output from running the Decision Tree for one student-term."""
    student_name: str
    student_id: str
    program: str
    term: str
    benefit_chapter: str

    weams_matched: bool = False
    weams_program: str = ""

    course_results: list = field(default_factory=list)  # list of CourseResult

    # Aggregates (computed after all courses processed)
    total_enrolled_units: float = 0.0
    total_certifiable_units: float = 0.0
    residential_units: float = 0.0
    distance_units: float = 0.0
    remedial_units: float = 0.0
    training_time: Optional[TrainingTime] = None
    rate_of_pursuit: float = 0.0
    mha_eligible: bool = False

    sco_queue_items: list = field(default_factory=list)  # courses needing SCO review


# ---------------------------------------------------------------------------
# WEAMS lookup — LIVE DATA (multi-institution)
# ---------------------------------------------------------------------------
# WEAMS-approved programs scraped from the VA GI Bill Comparison Tool
# on April 10, 2026. Supports multiple CSU campuses via facility code:
#   - SDSU (11910105): 531 programs
#   - CSUN (11918105): 322 programs
#
# The full program lists + matching logic lives in weams_programs.py.
# This wrapper adapts it to return the WEAMSProgram dataclass used by the tree.

from weams_programs import match_weams_program as _weams_match


def match_weams_program(declared_program: str, facility_code: str = "11910105") -> Optional[WEAMSProgram]:
    """
    Match a student's declared program against real WEAMS entries.

    Uses the weams_programs module which supports:
      - Exact match after normalization
      - Structured parsing of PS formats (e.g. "Journalism (BA)", "B.A. Journalism")
      - Fuzzy keyword overlap with confidence scoring
      - Multi-institution lookup via facility code

    Returns a WEAMSProgram dataclass or None.
    LOW confidence matches route to SCO queue via HITL escalation.
    """
    result = _weams_match(declared_program, facility_code)
    if result is None:
        return None

    weams_name, confidence = result

    # Build WEAMSProgram with the matched WEAMS entry
    # Parse degree prefix for the CIP code placeholder
    parts = weams_name.split(" ", 1)
    degree_prefix = parts[0] if len(parts) > 1 else ""
    subject = parts[1] if len(parts) > 1 else weams_name

    wp = WEAMSProgram(
        description=weams_name,
        code=f"{degree_prefix}-WEAMS",  # placeholder until real CIP mapping
        effective_start="2000-01-01",
        effective_end=None,
        active=True,
    )
    # Attach confidence for HITL escalation checks
    wp._match_confidence = confidence
    return wp


# ---------------------------------------------------------------------------
# The 7-Step Decision Tree
# ---------------------------------------------------------------------------

def run_decision_tree(student: StudentInput) -> DecisionTreeOutput:
    """
    Run the 7-step Course Applicability Decision Tree for one student-term.

    Steps 1-5 determine IF each course is certifiable.
    Step 6 classifies HOW (residential vs distance).
    Step 7 computes overall rate of pursuit / training time.
    """

    output = DecisionTreeOutput(
        student_name=student.name,
        student_id=student.student_id,
        program=student.program,
        term=student.term,
        benefit_chapter=student.benefit_chapter,
    )

    # -----------------------------------------------------------------------
    # STEP 1: WEAMS Program Match (student-level, not per-course)
    # -----------------------------------------------------------------------
    # "Before evaluating any individual course, the system must confirm the
    #  student's declared degree program exists in the WEAMS 1998 report for
    #  the student's institution and is currently active."

    weams_match = match_weams_program(student.program, student.facility_code)

    if weams_match is None:
        # STOP — no courses can be certified
        output.weams_matched = False
        for course in student.courses:
            output.course_results.append(CourseResult(
                course_id=course.course_id,
                title=course.title,
                units=course.units,
                certifiable=False,
                exclusion_reason=CourseExclReason.NOT_IN_WEAMS,
                exclusion_detail=f"'{student.program}' not found in WEAMS for Facility Code 11910105",
                step_failed=1,
            ))
        output.total_enrolled_units = sum(c.units for c in student.courses)
        return output

    if not weams_match.active:
        output.weams_matched = False
        for course in student.courses:
            output.course_results.append(CourseResult(
                course_id=course.course_id,
                title=course.title,
                units=course.units,
                certifiable=False,
                exclusion_reason=CourseExclReason.WEAMS_WITHDRAWN,
                exclusion_detail=f"Program withdrawn from WEAMS effective {weams_match.effective_end}",
                step_failed=1,
            ))
        output.total_enrolled_units = sum(c.units for c in student.courses)
        return output

    output.weams_matched = True
    output.weams_program = weams_match.description

    # -----------------------------------------------------------------------
    # STEPS 2-6: Per-course evaluation
    # -----------------------------------------------------------------------

    for course in student.courses:
        result = _evaluate_course(course, student)
        output.course_results.append(result)

        if not result.certifiable and result.exclusion_reason == CourseExclReason.SCO_EXCEPTION:
            output.sco_queue_items.append(result)

    # -----------------------------------------------------------------------
    # STEP 7: Rate of Pursuit / Training Time
    # -----------------------------------------------------------------------

    output.total_enrolled_units = sum(c.units for c in student.courses)
    output.total_certifiable_units = sum(
        r.units for r in output.course_results if r.certifiable
    )
    output.residential_units = sum(
        r.units for r in output.course_results
        if r.certifiable and r.modality == Modality.RESIDENTIAL
    )
    output.distance_units = sum(
        r.units for r in output.course_results
        if r.certifiable and r.modality == Modality.DISTANCE
    )

    # Check special full-time triggers (799A, 897, 899)
    special_full_time = (
        student.enrolled_in_799a or
        student.enrolled_in_897 or
        student.enrolled_in_899
    )

    if special_full_time:
        output.training_time = TrainingTime.FULL_TIME
        output.rate_of_pursuit = 1.0
        output.mha_eligible = True
    else:
        output.training_time, output.rate_of_pursuit = _compute_training_time(
            output.total_certifiable_units, student.academic_level
        )

    # MHA eligibility: Ch33 only, need RoP > 50% AND at least some R units
    # (simplified — full MHA rules are more complex but this covers the basics)
    if student.benefit_chapter == "ch33":
        output.mha_eligible = (
            output.rate_of_pursuit > 0.50 and output.residential_units > 0
        )
    else:
        output.mha_eligible = False  # MHA is Ch33-specific

    return output


def _evaluate_course(course: CourseSchedule, student: StudentInput) -> CourseResult:
    """
    Run Steps 2-6 for a single course.
    Returns a CourseResult with certifiable status and modality.
    """

    result = CourseResult(
        course_id=course.course_id,
        title=course.title,
        units=course.units,
        certifiable=False,  # default — must pass all steps to become True
    )

    # -------------------------------------------------------------------
    # STEP 2: Degree Applicability (DARS check)
    # -------------------------------------------------------------------
    # "The system checks the student's DARS to see if the course fulfills
    #  any requirement in their approved program."

    if not course.in_dars:
        # Check for SCO exceptions (rounding out, advisor approval, substitution)
        if course.has_sco_exception:
            result.flags.append(
                f"SCO exception: {course.sco_exception_type}"
            )
            # SCO exceptions still need SCO review — route to queue
            result.certifiable = False
            result.exclusion_reason = CourseExclReason.SCO_EXCEPTION
            result.exclusion_detail = (
                f"Not in DARS. SCO exception ({course.sco_exception_type}) "
                f"requires manual review."
            )
            result.step_failed = 2
            return result
        else:
            # Not in DARS, no exception → excluded
            result.exclusion_reason = CourseExclReason.NOT_IN_DARS
            result.exclusion_detail = (
                f"Course not required for {student.program} per DARS. "
                f"No SCO exception on file."
            )
            result.step_failed = 2
            return result

    # -------------------------------------------------------------------
    # STEP 3: Audit Check
    # -------------------------------------------------------------------
    # "Audited courses cannot be certified."

    if course.grading_basis == GradingBasis.AUDIT:
        result.exclusion_reason = CourseExclReason.AUDIT_COURSE
        result.exclusion_detail = (
            "Audited courses cannot be certified per SCO Handbook Rev 7.4."
        )
        result.step_failed = 3
        return result

    # -------------------------------------------------------------------
    # STEP 4: Repeat Check
    # -------------------------------------------------------------------
    # "Classes that are successfully completed may not be certified again."
    # Exceptions: failed, higher grade req, school requires retake.

    if course.previously_passed and not course.repeat_exception:
        result.exclusion_reason = CourseExclReason.REPEAT_PASSING
        result.exclusion_detail = (
            "Previously passed. No qualifying repeat exception. "
            "Routed to SCO for review."
        )
        result.step_failed = 4
        result.flags.append("SCO review: verify if repeat exception applies")
        return result

    # -------------------------------------------------------------------
    # STEP 5: Remedial / Deficiency Check
    # -------------------------------------------------------------------
    # "Remedial and deficiency courses offered in an online or hybrid format
    #  cannot be approved for VA benefits and cannot be certified to VA
    #  under any chapter." — SCO Handbook Rev 7.4
    #
    # 100% in-person remedial = certifiable (if documented need)
    # Online or hybrid remedial = NEVER certifiable

    if course.is_remedial:
        if course.all_online or not course.has_in_person_session:
            # Online remedial = never certifiable
            result.exclusion_reason = CourseExclReason.REMEDIAL_ONLINE
            result.exclusion_detail = (
                "Remedial/deficiency course in online or hybrid format. "
                "Cannot be certified under any chapter per Handbook Rev 7.4."
            )
            result.step_failed = 5
            return result
        else:
            # In-person remedial = certifiable, but flag for documentation
            result.flags.append(
                "Remedial course — verify documented need (test/placement records)"
            )

    # -------------------------------------------------------------------
    # STEP 6: Modality Classification
    # -------------------------------------------------------------------
    # Determines HOW the course is reported, not WHETHER.
    # Practicum/internship = always residential per handbook.
    # Hybrid with ≥1 required 50-min in-person session during term = residential.
    # Pre-term only meetings = distance.
    # All online = distance.

    if course.is_practicum:
        result.modality = Modality.RESIDENTIAL
        result.flags.append(
            "Practicum/internship — classified as residential per handbook"
        )
    elif course.all_online:
        result.modality = Modality.DISTANCE
    elif course.is_pre_term_only:
        # In-person meeting before term starts — must report as distance
        result.modality = Modality.DISTANCE
        result.flags.append(
            "Pre-term in-person only — classified as distance per Handbook Example 5"
        )
    elif course.has_in_person_session:
        # At least one required 50-min+ in-person session during term
        result.modality = Modality.RESIDENTIAL
    else:
        # Default: if we can't confirm in-person, classify as distance
        result.modality = Modality.DISTANCE
        result.flags.append(
            "Could not confirm in-person session — defaulted to distance"
        )

    # If we got here, the course passed all 5 gates
    result.certifiable = True
    return result


def _compute_training_time(
    certifiable_units: float, level: AcademicLevel
) -> tuple[TrainingTime, float]:
    """
    Compute training time and rate of pursuit from certifiable units.

    Undergraduate (SCO Handbook):
      12+ = full-time, 9-11 = 3/4, 6-8 = 1/2, 4-5 = <1/2, 1-3 = 1/4 or less

    Graduate — SDSU definitions:
      Master's: 9+ = full-time
      Doctoral: 6+ = full-time

    Rate of Pursuit = certifiable_units / full_time_units
    """

    if level == AcademicLevel.UNDERGRADUATE:
        full_time_units = 12.0
        rop = certifiable_units / full_time_units if full_time_units > 0 else 0

        if certifiable_units >= 12:
            return TrainingTime.FULL_TIME, min(rop, 1.0)
        elif certifiable_units >= 9:
            return TrainingTime.THREE_QUARTER, rop
        elif certifiable_units >= 6:
            return TrainingTime.HALF_TIME, rop
        elif certifiable_units >= 4:
            return TrainingTime.LESS_THAN_HALF, rop
        else:
            return TrainingTime.QUARTER_OR_LESS, rop

    elif level == AcademicLevel.MASTERS:
        full_time_units = 9.0
        rop = certifiable_units / full_time_units if full_time_units > 0 else 0

        if certifiable_units >= 9:
            return TrainingTime.FULL_TIME, min(rop, 1.0)
        elif certifiable_units >= 7:
            return TrainingTime.THREE_QUARTER, rop
        elif certifiable_units >= 5:
            return TrainingTime.HALF_TIME, rop
        else:
            return TrainingTime.LESS_THAN_HALF, rop

    elif level == AcademicLevel.DOCTORAL:
        full_time_units = 6.0
        rop = certifiable_units / full_time_units if full_time_units > 0 else 0

        if certifiable_units >= 6:
            return TrainingTime.FULL_TIME, min(rop, 1.0)
        elif certifiable_units >= 4:
            return TrainingTime.THREE_QUARTER, rop
        elif certifiable_units >= 3:
            return TrainingTime.HALF_TIME, rop
        else:
            return TrainingTime.LESS_THAN_HALF, rop

    # Fallback
    return TrainingTime.LESS_THAN_HALF, 0.0


# ---------------------------------------------------------------------------
# Pretty-print output
# ---------------------------------------------------------------------------

def print_results(output: DecisionTreeOutput):
    """Print a readable summary of the Decision Tree results."""

    print("=" * 70)
    print(f"  VA COURSE APPLICABILITY — DECISION TREE RESULTS")
    print("=" * 70)
    print(f"  Student:   {output.student_name} ({output.student_id})")
    print(f"  Program:   {output.program}")
    print(f"  Term:      {output.term}")
    print(f"  Chapter:   {output.benefit_chapter.upper()}")
    print(f"  WEAMS:     {'MATCHED' if output.weams_matched else 'NOT FOUND'}"
          f" — {output.weams_program}")
    print("-" * 70)

    # Per-course results
    print(f"\n  {'COURSE':<12} {'UNITS':>5}  {'CERTIFIABLE':>11}  "
          f"{'MODALITY':>12}  REASON")
    print(f"  {'-'*12} {'-'*5}  {'-'*11}  {'-'*12}  {'-'*30}")

    for r in output.course_results:
        cert_str = "YES" if r.certifiable else "NO"
        mod_str = r.modality.value.upper() if r.modality else "—"
        reason = ""
        if r.certifiable:
            reason = r.flags[0] if r.flags else ""
        else:
            reason = r.exclusion_reason.value if r.exclusion_reason else ""

        print(f"  {r.course_id:<12} {r.units:>5.1f}  {cert_str:>11}  "
              f"{mod_str:>12}  {reason}")

    # Totals
    print(f"\n{'-' * 70}")
    print(f"  ENROLLED:     {output.total_enrolled_units:.1f} units")
    print(f"  CERTIFIABLE:  {output.total_certifiable_units:.1f} units"
          f"  (R:{output.residential_units:.0f}, D:{output.distance_units:.0f})")
    print(f"  TRAINING:     {output.training_time.value.replace('_', ' ').title()}"
          f"  (RoP: {output.rate_of_pursuit:.0%})")
    print(f"  MHA ELIGIBLE: {'YES' if output.mha_eligible else 'NO'}")

    if output.sco_queue_items:
        print(f"\n  SCO QUEUE ({len(output.sco_queue_items)} items):")
        for item in output.sco_queue_items:
            print(f"    - {item.course_id}: {item.exclusion_detail}")

    print("=" * 70)


# ---------------------------------------------------------------------------
# JAMES ROSTER TEST CASE
# ---------------------------------------------------------------------------

def james_roster_test():
    """
    Canonical regression test.

    Student: Daniel Bahena (James Roster case), B.A. Journalism, Ch.33, Fall 2024

    Courses:
      ENS 331  (3.0) — ALL ONLINE, NOT in DARS → EXCLUDED
      MIS 401  (3.0) — Tu ONLINE + Th in NE 173 → Hybrid → RESIDENTIAL, in DARS
      MIS 460  (3.0) — Th in SSW 2501 only → RESIDENTIAL, in DARS
      MIS 585  (3.0) — ALL ONLINE → DISTANCE, in DARS
      MUSIC 151 (3.0) — ALL ONLINE → DISTANCE, in DARS

    Expected: R:6, D:6, T:12, ENS 331 excluded
    """

    student = StudentInput(
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
                in_dars=False,           # NOT required for B.A. Journalism
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
                has_in_person_session=True,  # Th in NE 173 (physical room)
            ),
            CourseSchedule(
                course_id="MIS 460",
                title="Business Application Development",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                all_online=False,
                has_in_person_session=True,  # Th in SSW 2501
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

    # Run the Decision Tree
    output = run_decision_tree(student)

    # Print results
    print_results(output)

    # -----------------------------------------------------------------------
    # REGRESSION ASSERTIONS
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

    # Core assertions from the spec
    check("WEAMS matched", output.weams_matched, True)
    check("Total enrolled", output.total_enrolled_units, 15.0)
    check("Total certifiable", output.total_certifiable_units, 12.0)
    check("Residential units", output.residential_units, 6.0)
    check("Distance units", output.distance_units, 6.0)
    check("Training time", output.training_time, TrainingTime.FULL_TIME)
    check("Rate of pursuit", output.rate_of_pursuit, 1.0)
    check("MHA eligible", output.mha_eligible, True)

    # Per-course checks
    results_by_id = {r.course_id: r for r in output.course_results}

    check("ENS 331 certifiable", results_by_id["ENS 331"].certifiable, False)
    check("ENS 331 reason", results_by_id["ENS 331"].exclusion_reason,
          CourseExclReason.NOT_IN_DARS)
    check("ENS 331 step failed", results_by_id["ENS 331"].step_failed, 2)

    check("MIS 401 certifiable", results_by_id["MIS 401"].certifiable, True)
    check("MIS 401 modality", results_by_id["MIS 401"].modality,
          Modality.RESIDENTIAL)

    check("MIS 460 certifiable", results_by_id["MIS 460"].certifiable, True)
    check("MIS 460 modality", results_by_id["MIS 460"].modality,
          Modality.RESIDENTIAL)

    check("MIS 585 certifiable", results_by_id["MIS 585"].certifiable, True)
    check("MIS 585 modality", results_by_id["MIS 585"].modality,
          Modality.DISTANCE)

    check("MUSIC 151 certifiable", results_by_id["MUSIC 151"].certifiable, True)
    check("MUSIC 151 modality", results_by_id["MUSIC 151"].modality,
          Modality.DISTANCE)

    print(f"\n    {checks_passed}/{checks_total} checks passed.")

    if checks_passed == checks_total:
        print("\n    *** JAMES ROSTER TEST CASE: ALL CHECKS PASSED ***")
    else:
        print(f"\n    *** JAMES ROSTER TEST CASE: {checks_total - checks_passed} FAILURES ***")

    return output


def kitchen_sink_test():
    """
    Synthetic test case — exercises every gate in the Decision Tree.

    Fake student: "Test Student A", B.S. Computer Science, Ch.35, Spring 2025

    Courses (8 total — designed to hit every branch):
      CS 101   (3.0) — in DARS, residential, normal         → CERTIFIABLE (R)
      CS 201   (3.0) — in DARS, distance, normal             → CERTIFIABLE (D)
      ART 100  (3.0) — in DARS, AUDIT grading basis          → EXCLUDED Step 3
      CS 150   (3.0) — in DARS, previously passed, no excep  → EXCLUDED Step 4
      CS 155   (3.0) — in DARS, previously FAILED, retaking  → CERTIFIABLE (repeat exception)
      MATH 090 (3.0) — in DARS, remedial, ALL ONLINE         → EXCLUDED Step 5
      MATH 091 (3.0) — in DARS, remedial, 100% in-person     → CERTIFIABLE (R, flagged)
      HIST 200 (3.0) — NOT in DARS, has SCO exception        → SCO QUEUE (Step 2)
      PHIL 300 (3.0) — in DARS, pre-term-only in-person      → CERTIFIABLE (D, flagged)

    Expected totals:
      Enrolled = 27.0
      Certifiable = 15.0  (CS 101 3R + CS 201 3D + CS 155 3R + MATH 091 3R + PHIL 300 3D)
      R = 9.0, D = 6.0
      Training time = Full-time (15 ≥ 12 UG threshold)
      Excluded: ART 100 (audit), CS 150 (repeat), MATH 090 (remedial online), HIST 200 (SCO queue)
    """

    student = StudentInput(
        name="Test Student A",
        student_id="KS-001",
        program="B.S. Computer Science",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch35",
        term="Spring 2025",
        courses=[
            # Normal residential — passes everything
            CourseSchedule(
                course_id="CS 101",
                title="Intro to Computer Science",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            # Normal distance — passes everything
            CourseSchedule(
                course_id="CS 201",
                title="Data Structures",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                all_online=True,
                has_in_person_session=False,
            ),
            # STEP 3 TRIGGER: Audit course
            CourseSchedule(
                course_id="ART 100",
                title="Introduction to Art",
                units=3.0,
                grading_basis=GradingBasis.AUDIT,
                in_dars=True,
                dars_rationale="GE area",
                has_in_person_session=True,
                all_online=False,
            ),
            # STEP 4 TRIGGER: Repeat of passed course, no exception
            CourseSchedule(
                course_id="CS 150",
                title="Intro to Programming",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                previously_passed=True,
                repeat_exception=False,
                has_in_person_session=True,
                all_online=False,
            ),
            # STEP 4 EXCEPTION: Repeat of FAILED course — should pass
            CourseSchedule(
                course_id="CS 155",
                title="Discrete Mathematics",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                previously_passed=True,
                repeat_exception=True,  # Failed previously
                has_in_person_session=True,
                all_online=False,
            ),
            # STEP 5 TRIGGER: Remedial + online = NEVER certifiable
            CourseSchedule(
                course_id="MATH 090",
                title="Basic Math Skills",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="remedial requirement",
                is_remedial=True,
                all_online=True,
                has_in_person_session=False,
            ),
            # STEP 5 PASS: Remedial + 100% in-person = certifiable
            CourseSchedule(
                course_id="MATH 091",
                title="Fundamental Algebra",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="remedial requirement",
                is_remedial=True,
                all_online=False,
                has_in_person_session=True,
            ),
            # STEP 2 TRIGGER: Not in DARS but has SCO exception → queue
            CourseSchedule(
                course_id="HIST 200",
                title="World History",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=False,
                has_sco_exception=True,
                sco_exception_type="advisor approval",
                has_in_person_session=True,
                all_online=False,
            ),
            # STEP 6 EDGE: Pre-term-only in-person → distance
            CourseSchedule(
                course_id="PHIL 300",
                title="Ethics in Technology",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="GE area",
                all_online=False,
                has_in_person_session=False,
                is_pre_term_only=True,
            ),
        ],
    )

    output = run_decision_tree(student)
    print_results(output)

    # -----------------------------------------------------------------------
    # REGRESSION ASSERTIONS
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

    r = {cr.course_id: cr for cr in output.course_results}

    # Aggregate checks
    check("WEAMS matched", output.weams_matched, True)
    check("Total enrolled", output.total_enrolled_units, 27.0)
    check("Total certifiable", output.total_certifiable_units, 15.0)
    check("Residential units", output.residential_units, 9.0)
    check("Distance units", output.distance_units, 6.0)
    check("Training time", output.training_time, TrainingTime.FULL_TIME)

    # Step 3: Audit gate
    check("ART 100 certifiable", r["ART 100"].certifiable, False)
    check("ART 100 reason", r["ART 100"].exclusion_reason, CourseExclReason.AUDIT_COURSE)
    check("ART 100 step failed", r["ART 100"].step_failed, 3)

    # Step 4: Repeat gate (blocked)
    check("CS 150 certifiable", r["CS 150"].certifiable, False)
    check("CS 150 reason", r["CS 150"].exclusion_reason, CourseExclReason.REPEAT_PASSING)
    check("CS 150 step failed", r["CS 150"].step_failed, 4)

    # Step 4: Repeat exception (passes)
    check("CS 155 certifiable", r["CS 155"].certifiable, True)
    check("CS 155 modality", r["CS 155"].modality, Modality.RESIDENTIAL)

    # Step 5: Remedial online (blocked)
    check("MATH 090 certifiable", r["MATH 090"].certifiable, False)
    check("MATH 090 reason", r["MATH 090"].exclusion_reason, CourseExclReason.REMEDIAL_ONLINE)
    check("MATH 090 step failed", r["MATH 090"].step_failed, 5)

    # Step 5: Remedial in-person (passes, flagged)
    check("MATH 091 certifiable", r["MATH 091"].certifiable, True)
    check("MATH 091 modality", r["MATH 091"].modality, Modality.RESIDENTIAL)
    check("MATH 091 remedial flag", "Remedial" in r["MATH 091"].flags[0], True)

    # Step 2: SCO exception queue
    check("HIST 200 certifiable", r["HIST 200"].certifiable, False)
    check("HIST 200 reason", r["HIST 200"].exclusion_reason, CourseExclReason.SCO_EXCEPTION)
    check("HIST 200 in SCO queue", len(output.sco_queue_items), 1)

    # Step 6 edge: Pre-term only → distance
    check("PHIL 300 certifiable", r["PHIL 300"].certifiable, True)
    check("PHIL 300 modality", r["PHIL 300"].modality, Modality.DISTANCE)

    # Normal courses
    check("CS 101 certifiable", r["CS 101"].certifiable, True)
    check("CS 101 modality", r["CS 101"].modality, Modality.RESIDENTIAL)
    check("CS 201 certifiable", r["CS 201"].certifiable, True)
    check("CS 201 modality", r["CS 201"].modality, Modality.DISTANCE)

    # MHA: Ch35 = no MHA
    check("MHA eligible (ch35)", output.mha_eligible, False)

    print(f"\n    {checks_passed}/{checks_total} checks passed.")

    if checks_passed == checks_total:
        print("\n    *** KITCHEN SINK TEST CASE: ALL CHECKS PASSED ***")
    else:
        print(f"\n    *** KITCHEN SINK TEST CASE: {checks_total - checks_passed} FAILURES ***")

    return output


def grad_thesis_test():
    """
    Graduate student test case — proves grad thresholds and 799A override.

    Fake student: "Test Student B", Master's City Planning, Ch.33, Fall 2025

    Courses (3 total, only 6 units — below Master's full-time of 9):
      CP 630   (3.0) — in DARS, residential    → CERTIFIABLE (R)
      CP 700   (3.0) — in DARS, distance        → CERTIFIABLE (D)
      THES 799A(3.0) — in DARS, residential     → CERTIFIABLE (R), triggers full-time

    Without 799A: 6 certifiable = half-time for Master's (5-8.9 range)
    With 799A: full-time override regardless of unit count

    Expected: R:6, D:3, T:9, full-time, MHA eligible
    """

    student = StudentInput(
        name="Test Student B",
        student_id="GT-001",
        program="Master of City Planning",
        academic_level=AcademicLevel.MASTERS,
        benefit_chapter="ch33",
        term="Fall 2025",
        enrolled_in_799a=True,
        courses=[
            CourseSchedule(
                course_id="CP 630",
                title="Urban Planning Theory",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="CP 700",
                title="Planning Research Methods",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                all_online=True,
                has_in_person_session=False,
            ),
            CourseSchedule(
                course_id="THES 799A",
                title="Thesis",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="thesis requirement",
                has_in_person_session=True,
                all_online=False,
            ),
        ],
    )

    output = run_decision_tree(student)
    print_results(output)

    # -----------------------------------------------------------------------
    # REGRESSION ASSERTIONS
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

    r = {cr.course_id: cr for cr in output.course_results}

    check("WEAMS matched", output.weams_matched, True)
    check("Total enrolled", output.total_enrolled_units, 9.0)
    check("Total certifiable", output.total_certifiable_units, 9.0)
    check("Residential units", output.residential_units, 6.0)
    check("Distance units", output.distance_units, 3.0)

    # THE KEY CHECK: 799A forces full-time even though 9 units alone
    # would be full-time for Master's — but the override is the mechanism
    check("Training time (799A override)", output.training_time, TrainingTime.FULL_TIME)
    check("Rate of pursuit", output.rate_of_pursuit, 1.0)
    check("MHA eligible", output.mha_eligible, True)

    # Per-course
    check("CP 630 certifiable", r["CP 630"].certifiable, True)
    check("CP 630 modality", r["CP 630"].modality, Modality.RESIDENTIAL)
    check("CP 700 certifiable", r["CP 700"].certifiable, True)
    check("CP 700 modality", r["CP 700"].modality, Modality.DISTANCE)
    check("THES 799A certifiable", r["THES 799A"].certifiable, True)
    check("THES 799A modality", r["THES 799A"].modality, Modality.RESIDENTIAL)

    print(f"\n    {checks_passed}/{checks_total} checks passed.")

    if checks_passed == checks_total:
        print("\n    *** GRAD THESIS TEST CASE: ALL CHECKS PASSED ***")
    else:
        print(f"\n    *** GRAD THESIS TEST CASE: {checks_total - checks_passed} FAILURES ***")

    return output


# ---------------------------------------------------------------------------
# RUN ALL TESTS
# ---------------------------------------------------------------------------

def run_all_tests():
    """Run the full regression suite."""
    print("\n" + "=" * 70)
    print("  RUNNING FULL REGRESSION SUITE — 3 TEST CASES")
    print("=" * 70 + "\n")

    print("\n>>> TEST 1: JAMES ROSTER (canonical — happy path)\n")
    james_roster_test()

    print("\n\n>>> TEST 2: KITCHEN SINK (synthetic — every gate fires)\n")
    kitchen_sink_test()

    print("\n\n>>> TEST 3: GRAD THESIS (Master's + 799A full-time override)\n")
    grad_thesis_test()

    print("\n" + "=" * 70)
    print("  REGRESSION SUITE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
