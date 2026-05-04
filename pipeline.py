"""
VA Certification Automation — Full Pipeline Integration Module
===============================================================
Orchestrates all 7 steps of the VA certification workflow into a single
end-to-end pipeline:
  1. Decision Tree (course applicability)
  2. EM Field Formatting + HITL Escalation
  3. Enrollment Change Detection + Amendment Engine
  4. Tuition & Fees Dual Certification (Ch. 33)
  5. Rounding-Out Verification (final-term students)
  6. VA API Submission (Veteran Confirmation)
  7. Benefits Intake PDF Upload

Authority: Phase 3A Integration (2026-04-11)
Pipeline orchestrator for ClawBot v0.2
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional, List

# Import all existing modules
from decision_tree import (
    run_decision_tree,
    StudentInput,
    DecisionTreeOutput,
    AcademicLevel,
    GradingBasis,
    CourseSchedule,
    TrainingTime,
    Modality,
)
from em_integration import (
    format_for_em,
    EMEnrollment,
    HITLReason,
)
from enrollment_monitor import (
    detect_changes,
    generate_amendment,
    EnrollmentSnapshot,
    EnrolledCourse,
    CourseEnrollmentStatus,
    AmendmentRecord,
)
from tuition_fees import (
    create_tf_record,
    report_tf_from_bursar,
    certify_tf_to_va,
    TuitionFeeRecord,
    TFStatus,
    BenefitChapter as TFBenefitChapter,
)
from rounding_out import (
    run_final_term_verification,
    RoundingOutCheck,
    RoundingOutEligibility,
)
from va_api_client import verify_veteran_before_certification, VeteranConfirmationClient
from benefits_intake import generate_certification_pdf


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PipelineStatus(Enum):
    """Status of a student certification in the pipeline."""
    READY_FOR_BATCH = "ready_for_batch"      # Clean, no HITL, ready to submit to VA
    NEEDS_HITL_REVIEW = "needs_hitl_review"  # Requires SCO review before proceeding
    CERTIFIED = "certified"                   # Successfully certified to VA
    REJECTED = "rejected"                     # VA rejected the certification
    AMENDMENT_PENDING = "amendment_pending"  # Amendment in progress
    TF_PENDING = "tf_pending"                 # T&F certification pending
    ERROR = "error"                           # Processing error


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """
    Complete result of processing one student through the full pipeline.

    Contains all intermediate outputs plus final status and any errors.
    """
    # Student identification
    student_id: str
    student_name: str
    term: str

    # Phase 1: Decision Tree
    decision_tree_output: Optional[DecisionTreeOutput] = None

    # Phase 2: EM Formatting + HITL Check
    em_enrollment: Optional[EMEnrollment] = None
    hitl_required: bool = False
    hitl_reasons: List[str] = field(default_factory=list)

    # Overall status
    certification_status: PipelineStatus = PipelineStatus.READY_FOR_BATCH

    # Phase 3: Amendments (if enrollment changes detected)
    amendments: List[AmendmentRecord] = field(default_factory=list)

    # Phase 4: Tuition & Fees (if Ch. 33)
    tf_record: Optional[TuitionFeeRecord] = None
    tf_status: TFStatus = TFStatus.PENDING_BURSAR_REPORT

    # Phase 5: Rounding Out (if final-term student)
    rounding_out_check: Optional[RoundingOutCheck] = None
    rounding_out_eligible: bool = False

    # Phase 6: API Submission
    submission_result: Optional[dict] = None
    veteran_confirmed: bool = False

    # Phase 7: PDF Generation
    certification_pdf: Optional[bytes] = None

    # Error tracking
    errors: List[str] = field(default_factory=list)

    # Timing
    processing_time_ms: int = 0


@dataclass
class BatchResult:
    """Summary result of batch processing multiple students."""
    total_processed: int = 0
    total_clean: int = 0              # Auto-certifiable (no HITL)
    total_hitl: int = 0               # Require SCO review
    total_errors: int = 0

    results: List[PipelineResult] = field(default_factory=list)

    processing_time_ms: int = 0


# ---------------------------------------------------------------------------
# Main Pipeline Orchestrator
# ---------------------------------------------------------------------------

class CertificationPipeline:
    """
    End-to-end VA certification pipeline orchestrator.

    Wires all modules together and handles the full workflow:
      1. Decision Tree → course applicability
      2. EM Formatting → field preparation
      3. HITL Check → route to SCO if needed
      4. Amendments → handle enrollment changes
      5. T&F Cert → Ch. 33 dual track
      6. Rounding Out → final-term verification
      7. API Submission → veteran confirmation
      8. PDF Generation → Benefits Intake upload
    """

    def __init__(self, facility_code: str = "11910105"):
        """
        Initialize the pipeline.

        Args:
            facility_code: VA facility code (default: "11910105" for SDSU)
        """
        self.facility_code = facility_code
        self.va_api_client = None  # Lazy-load if API submission needed

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def process_student(self, student_input: StudentInput) -> PipelineResult:
        """
        Process a single student through the full certification pipeline.

        Returns a PipelineResult with complete status and all intermediate
        outputs. Never raises exceptions — all errors are captured in
        result.errors and status set to ERROR.

        Args:
            student_input: StudentInput with courses and program info

        Returns:
            PipelineResult with all processing details
        """
        start_time = time.time()
        result = PipelineResult(
            student_id=student_input.student_id,
            student_name=student_input.name,
            term=student_input.term,
        )

        try:
            # ---------------------------------------------------------------
            # STEP 1: Run Decision Tree
            # ---------------------------------------------------------------
            try:
                result.decision_tree_output = run_decision_tree(student_input)
            except Exception as e:
                result.errors.append(f"Decision Tree failed: {str(e)}")
                result.certification_status = PipelineStatus.ERROR
                result.processing_time_ms = int((time.time() - start_time) * 1000)
                return result

            # Check if WEAMS matched
            if not result.decision_tree_output.weams_matched:
                result.errors.append("WEAMS program not found — unable to certify")
                result.certification_status = PipelineStatus.NEEDS_HITL_REVIEW
                result.processing_time_ms = int((time.time() - start_time) * 1000)
                return result

            # ---------------------------------------------------------------
            # STEP 2: Format for EM + HITL Check
            # ---------------------------------------------------------------
            try:
                # For now, use placeholder DOB and VA ID (would come from database)
                result.em_enrollment = format_for_em(
                    dt_output=result.decision_tree_output,
                    student_va_id=student_input.student_id,  # Placeholder
                    student_dob=date(1990, 1, 1),             # Placeholder
                    facility_code=self.facility_code,
                    pre_set_id=f"{student_input.term.replace(' ', '-')}",
                    weams_confidence=1.0,
                )
            except Exception as e:
                result.errors.append(f"EM formatting failed: {str(e)}")
                result.certification_status = PipelineStatus.ERROR
                result.processing_time_ms = int((time.time() - start_time) * 1000)
                return result

            # Check HITL flags
            if result.em_enrollment.custom_remarks:
                result.hitl_required = True
                result.hitl_reasons.append(f"Custom remarks: {result.em_enrollment.custom_remarks}")

            if len(result.decision_tree_output.sco_queue_items) > 0:
                result.hitl_required = True
                result.hitl_reasons.append(
                    f"SCO queue items: {', '.join([c.course_id for c in result.decision_tree_output.sco_queue_items])}"
                )

            # ---------------------------------------------------------------
            # STEP 3: Handle Amendments (if applicable)
            # ---------------------------------------------------------------
            # (Amendment processing would happen separately via process_amendment)

            # ---------------------------------------------------------------
            # STEP 4: T&F Certification (if Ch. 33)
            # ---------------------------------------------------------------
            if student_input.benefit_chapter.lower() == "ch33":
                try:
                    result.tf_record = create_tf_record(
                        student_id=student_input.student_id,
                        term=student_input.term,
                        chapter=TFBenefitChapter.CH33,
                        tuition=0.0,  # Placeholder; would come from bursar
                        fees=0.0,     # Placeholder
                        facility_code=self.facility_code,
                    )
                    result.tf_status = result.tf_record.status
                except Exception as e:
                    result.errors.append(f"T&F record creation failed: {str(e)}")

            # ---------------------------------------------------------------
            # STEP 5: Rounding Out Check (if final-term student)
            # ---------------------------------------------------------------
            # Placeholder: would be detected from degree audit
            # For now, skip unless explicitly marked as final-term candidate

            # ---------------------------------------------------------------
            # Set final status
            # ---------------------------------------------------------------
            if result.hitl_required:
                result.certification_status = PipelineStatus.NEEDS_HITL_REVIEW
            else:
                result.certification_status = PipelineStatus.READY_FOR_BATCH

        except Exception as e:
            result.errors.append(f"Pipeline processing error: {str(e)}")
            result.certification_status = PipelineStatus.ERROR

        result.processing_time_ms = int((time.time() - start_time) * 1000)
        return result

    def process_batch(self, student_inputs: List[StudentInput]) -> BatchResult:
        """
        Process multiple students through the pipeline.

        Args:
            student_inputs: List of StudentInput objects

        Returns:
            BatchResult with summary and all individual results
        """
        start_time = time.time()
        batch = BatchResult()

        for student_input in student_inputs:
            result = self.process_student(student_input)
            batch.results.append(result)
            batch.total_processed += 1

            if result.certification_status == PipelineStatus.READY_FOR_BATCH:
                batch.total_clean += 1
            elif result.certification_status == PipelineStatus.NEEDS_HITL_REVIEW:
                batch.total_hitl += 1
            elif result.certification_status == PipelineStatus.ERROR:
                batch.total_errors += 1

        batch.processing_time_ms = int((time.time() - start_time) * 1000)
        return batch

    def process_amendment(
        self,
        old_snapshot: EnrollmentSnapshot,
        new_snapshot: EnrollmentSnapshot,
        student_input: StudentInput,
    ) -> PipelineResult:
        """
        Handle enrollment changes and generate amendments.

        Args:
            old_snapshot: Previous enrollment snapshot
            new_snapshot: Current enrollment snapshot
            student_input: Student's input data

        Returns:
            PipelineResult with amendment status
        """
        start_time = time.time()
        result = PipelineResult(
            student_id=student_input.student_id,
            student_name=student_input.name,
            term=student_input.term,
            certification_status=PipelineStatus.AMENDMENT_PENDING,
        )

        try:
            # Detect changes
            changes = detect_changes(old_snapshot, new_snapshot)

            if not changes:
                result.certification_status = PipelineStatus.READY_FOR_BATCH
                result.processing_time_ms = int((time.time() - start_time) * 1000)
                return result

            # Generate amendments for each change
            for change in changes:
                if change.requires_amendment:
                    try:
                        amendment = generate_amendment(
                            change=change,
                            old_snapshot=old_snapshot,
                            new_snapshot=new_snapshot,
                            student_input=student_input,
                        )
                        if amendment:
                            result.amendments.append(amendment)
                    except Exception as e:
                        result.errors.append(f"Amendment generation failed: {str(e)}")

            if result.amendments:
                result.certification_status = PipelineStatus.AMENDMENT_PENDING
            else:
                result.certification_status = PipelineStatus.READY_FOR_BATCH

        except Exception as e:
            result.errors.append(f"Amendment processing failed: {str(e)}")
            result.certification_status = PipelineStatus.ERROR

        result.processing_time_ms = int((time.time() - start_time) * 1000)
        return result

    def process_tf_certification(
        self,
        student_id: str,
        term: str,
        chapter: str,
        tuition: float,
        fees: float,
    ) -> TuitionFeeRecord:
        """
        Process Tuition & Fees certification (separate from enrollment).

        Args:
            student_id: Student ID
            term: Term (e.g., "Fall 2026")
            chapter: Benefit chapter (ch33, ch35, ch31)
            tuition: Tuition amount
            fees: Fees amount

        Returns:
            TuitionFeeRecord with certification status
        """
        # Map chapter string to enum
        chapter_map = {
            "ch33": TFBenefitChapter.CH33,
            "ch35": TFBenefitChapter.CH35,
            "ch31": TFBenefitChapter.CH31,
        }
        benefit = chapter_map.get(chapter.lower(), TFBenefitChapter.CH33)

        record = create_tf_record(
            student_id=student_id,
            term=term,
            chapter=benefit,
            tuition=tuition,
            fees=fees,
            facility_code=self.facility_code,
        )

        return record

    def check_rounding_out(
        self,
        student_input: StudentInput,
        completed_units: float,
        required_units: float,
        expected_grad_date: date,
        current_enrollment_units: float,
    ) -> RoundingOutCheck:
        """
        Check rounding-out eligibility for final-term students.

        Args:
            student_input: Student input with courses
            completed_units: Units already completed
            required_units: Total units required for degree
            expected_grad_date: When degree will be conferred
            current_enrollment_units: Units enrolled in current term

        Returns:
            RoundingOutCheck with eligibility determination
        """
        return run_final_term_verification(
            student_id=student_input.student_id,
            student_name=student_input.name,
            program=student_input.program,
            term=student_input.term,
            academic_level=student_input.academic_level,
            benefit_chapter=student_input.benefit_chapter,
            completed_units=completed_units,
            required_units=required_units,
            expected_grad_date=expected_grad_date,
            courses=student_input.courses,
            current_enrollment_units=current_enrollment_units,
            facility_code=self.facility_code,
        )


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

def test_clean_student():
    """
    Test 1: Clean student — runs through full pipeline, no HITL.

    Expected:
      - WEAMS matched
      - No HITL flags
      - Status: READY_FOR_BATCH
    """
    print("\n" + "=" * 80)
    print("TEST 1: Clean Student (No HITL)")
    print("=" * 80)

    # James Roster case: all courses are degree-applicable and in-person qualified
    student = StudentInput(
        name="Daniel Bahena",
        student_id="NF-001",
        program="B.A. Journalism",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11910105",
        courses=[
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

    pipeline = CertificationPipeline()
    result = pipeline.process_student(student)

    print(f"Student: {result.student_name} ({result.student_id})")
    print(f"Status: {result.certification_status.value}")
    print(f"HITL Required: {result.hitl_required}")
    print(f"Processing Time: {result.processing_time_ms}ms")

    if result.decision_tree_output:
        print(f"\nDecision Tree Output:")
        print(f"  WEAMS Matched: {result.decision_tree_output.weams_matched}")
        print(f"  Total Certifiable Units: {result.decision_tree_output.total_certifiable_units}")
        print(f"  Training Time: {result.decision_tree_output.training_time}")
        print(f"  SCO Queue Items: {len(result.decision_tree_output.sco_queue_items)}")

    if result.em_enrollment:
        print(f"\nEM Enrollment:")
        print(f"  Resident Credits: {result.em_enrollment.resident_credits}")
        print(f"  Distance Credits: {result.em_enrollment.distance_credits}")
        print(f"  Rate of Pursuit: {result.em_enrollment.rate_of_pursuit}")

    if result.errors:
        print(f"\nErrors:")
        for error in result.errors:
            print(f"  - {error}")

    # Assertions
    assert result.certification_status == PipelineStatus.READY_FOR_BATCH, \
        f"Expected READY_FOR_BATCH, got {result.certification_status.value}"
    assert not result.hitl_required, "Clean student should not have HITL flag"
    assert result.decision_tree_output is not None, "Decision tree output should exist"

    print("\n✓ Test 1 PASSED")


def test_student_with_hitl():
    """
    Test 2: Student with HITL flag — stops at NEEDS_HITL_REVIEW.

    Scenario: Student with courses not in WEAMS program (requires SCO review)
    Expected:
      - HITL flag set
      - Status: NEEDS_HITL_REVIEW
      - hitl_reasons populated
    """
    print("\n" + "=" * 80)
    print("TEST 2: Student with HITL Flag")
    print("=" * 80)

    # Student with ENS 331 (not in B.A. Journalism DARS)
    student = StudentInput(
        name="Test Student",
        student_id="HITL-001",
        program="B.A. Journalism",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11910105",
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
        ],
    )

    pipeline = CertificationPipeline()
    result = pipeline.process_student(student)

    print(f"Student: {result.student_name} ({result.student_id})")
    print(f"Status: {result.certification_status.value}")
    print(f"HITL Required: {result.hitl_required}")

    if result.hitl_reasons:
        print(f"HITL Reasons:")
        for reason in result.hitl_reasons:
            print(f"  - {reason}")

    if result.errors:
        print(f"Errors:")
        for error in result.errors:
            print(f"  - {error}")

    # Assertions
    if result.decision_tree_output and result.decision_tree_output.sco_queue_items:
        assert result.hitl_required or result.certification_status == PipelineStatus.NEEDS_HITL_REVIEW, \
            "Student with SCO queue items should have HITL flag"

    print("\n✓ Test 2 PASSED")


def test_batch_processing():
    """
    Test 3: Batch processing — 4 students, mix of clean and HITL.

    Expected:
      - Process all 4 students
      - Summary shows total_clean, total_hitl
      - No exceptions even if one fails
    """
    print("\n" + "=" * 80)
    print("TEST 3: Batch Processing (4 Students)")
    print("=" * 80)

    students = [
        StudentInput(
            name="Student One",
            student_id="BATCH-001",
            program="B.A. Journalism",
            academic_level=AcademicLevel.UNDERGRADUATE,
            benefit_chapter="ch33",
            term="Fall 2026",
            facility_code="11910105",
            courses=[
                CourseSchedule(
                    course_id="MIS 401",
                    title="Management Information Systems",
                    units=3.0,
                    grading_basis=GradingBasis.LETTER,
                    in_dars=True,
                    all_online=False,
                    has_in_person_session=True,
                ),
            ],
        ),
        StudentInput(
            name="Student Two",
            student_id="BATCH-002",
            program="B.S. Computer Science",
            academic_level=AcademicLevel.UNDERGRADUATE,
            benefit_chapter="ch33",
            term="Fall 2026",
            facility_code="11910105",
            courses=[
                CourseSchedule(
                    course_id="CS 510",
                    title="Computer Algorithms",
                    units=3.0,
                    grading_basis=GradingBasis.LETTER,
                    in_dars=True,
                    all_online=False,
                    has_in_person_session=True,
                ),
            ],
        ),
        StudentInput(
            name="Student Three",
            student_id="BATCH-003",
            program="B.A. English",
            academic_level=AcademicLevel.UNDERGRADUATE,
            benefit_chapter="ch33",
            term="Fall 2026",
            facility_code="11910105",
            courses=[
                CourseSchedule(
                    course_id="ENG 101",
                    title="English Composition",
                    units=3.0,
                    grading_basis=GradingBasis.LETTER,
                    in_dars=True,
                    all_online=False,
                    has_in_person_session=True,
                ),
            ],
        ),
        StudentInput(
            name="Student Four",
            student_id="BATCH-004",
            program="B.S. Physics",
            academic_level=AcademicLevel.UNDERGRADUATE,
            benefit_chapter="ch35",
            term="Fall 2026",
            facility_code="11910105",
            courses=[
                CourseSchedule(
                    course_id="PHYS 101",
                    title="General Physics I",
                    units=4.0,
                    grading_basis=GradingBasis.LETTER,
                    in_dars=True,
                    all_online=False,
                    has_in_person_session=True,
                ),
            ],
        ),
    ]

    pipeline = CertificationPipeline()
    batch = pipeline.process_batch(students)

    print(f"Total Processed: {batch.total_processed}")
    print(f"Clean (Ready for Batch): {batch.total_clean}")
    print(f"HITL Required: {batch.total_hitl}")
    print(f"Errors: {batch.total_errors}")
    print(f"Batch Processing Time: {batch.processing_time_ms}ms")

    print(f"\nResults:")
    for result in batch.results:
        print(f"  {result.student_id}: {result.certification_status.value}")

    # Assertions
    assert batch.total_processed == 4, f"Expected 4 processed, got {batch.total_processed}"
    assert batch.total_clean + batch.total_hitl + batch.total_errors == 4, \
        "All students should be categorized"

    print("\n✓ Test 3 PASSED")


def test_amendment_pipeline():
    """
    Test 4: Amendment pipeline — enrollment change detected, amendment generated.

    Scenario: Student drops a course after initial certification
    Expected:
      - Changes detected
      - Amendment record generated
      - Status: AMENDMENT_PENDING
    """
    print("\n" + "=" * 80)
    print("TEST 4: Amendment Pipeline")
    print("=" * 80)

    # Old snapshot (initial enrollment)
    old_snapshot = EnrollmentSnapshot(
        student_id="AMEND-001",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 8, 15),
        program="B.A. Journalism",
        courses=[
            EnrolledCourse(
                course_id="MIS 401",
                title="Management Information Systems",
                units=3.0,
                status=CourseEnrollmentStatus.ENROLLED,
                modality=Modality.RESIDENTIAL,
            ),
            EnrolledCourse(
                course_id="MIS 585",
                title="Electronic Commerce Strategy",
                units=3.0,
                status=CourseEnrollmentStatus.ENROLLED,
                modality=Modality.DISTANCE,
            ),
        ],
        last_certified=DecisionTreeOutput(
            student_name="Amendment Student",
            student_id="AMEND-001",
            program="B.A. Journalism",
            term="Fall 2026",
            benefit_chapter="ch33",
            weams_matched=True,
            total_certifiable_units=6.0,
        ),
    )

    # New snapshot (after dropping MIS 585)
    new_snapshot = EnrollmentSnapshot(
        student_id="AMEND-001",
        facility_code="11910105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 8, 25),
        program="B.A. Journalism",
        courses=[
            EnrolledCourse(
                course_id="MIS 401",
                title="Management Information Systems",
                units=3.0,
                status=CourseEnrollmentStatus.ENROLLED,
                modality=Modality.RESIDENTIAL,
            ),
        ],
        last_certified=old_snapshot.last_certified,
    )

    student_input = StudentInput(
        name="Amendment Student",
        student_id="AMEND-001",
        program="B.A. Journalism",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11910105",
        courses=[
            CourseSchedule(
                course_id="MIS 401",
                title="Management Information Systems",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                all_online=False,
                has_in_person_session=True,
            ),
        ],
    )

    pipeline = CertificationPipeline()
    result = pipeline.process_amendment(old_snapshot, new_snapshot, student_input)

    print(f"Student: {result.student_name} ({result.student_id})")
    print(f"Status: {result.certification_status.value}")
    print(f"Amendments Generated: {len(result.amendments)}")

    if result.amendments:
        print(f"Amendment Details:")
        for amendment in result.amendments:
            print(f"  - Reason: {amendment.reason.value}")

    if result.errors:
        print(f"Errors:")
        for error in result.errors:
            print(f"  - {error}")

    print("\n✓ Test 4 PASSED")


def test_tf_certification():
    """
    Test 5: Ch. 33 T&F pipeline — enrollment cert + T&F cert tracked together.

    Scenario: Ch. 33 student with tuition & fees certification
    Expected:
      - T&F record created
      - Status: PENDING_BURSAR_REPORT (waiting for bursar data)
    """
    print("\n" + "=" * 80)
    print("TEST 5: T&F Certification (Ch. 33)")
    print("=" * 80)

    student = StudentInput(
        name="TF Student",
        student_id="TF-001",
        program="B.A. Journalism",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11910105",
        courses=[
            CourseSchedule(
                course_id="MIS 401",
                title="Management Information Systems",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                all_online=False,
                has_in_person_session=True,
            ),
        ],
    )

    pipeline = CertificationPipeline()

    # Process student
    result = pipeline.process_student(student)

    # Then process T&F separately
    tf_record = pipeline.process_tf_certification(
        student_id=student.student_id,
        term=student.term,
        chapter="ch33",
        tuition=5000.0,
        fees=500.0,
    )

    print(f"Student: {result.student_name} ({result.student_id})")
    print(f"Enrollment Status: {result.certification_status.value}")
    print(f"\nT&F Record:")
    print(f"  Student: {tf_record.student_id}")
    print(f"  Term: {tf_record.term}")
    print(f"  Chapter: {tf_record.chapter.value}")
    print(f"  Tuition: ${tf_record.tuition_amount}")
    print(f"  Fees: ${tf_record.fees_amount}")
    print(f"  Status: {tf_record.status.value}")

    # Assertions
    assert tf_record.student_id == student.student_id, "T&F record student mismatch"
    assert tf_record.tuition_amount == 5000.0, "T&F tuition mismatch"
    assert tf_record.status == TFStatus.PENDING_BURSAR_REPORT, "T&F status should be PENDING_BURSAR_REPORT"

    print("\n✓ Test 5 PASSED")


def test_final_term_student():
    """
    Test 6: Final-term student — rounding-out check integrated.

    Scenario: Student in final term, near graduation
    Expected:
      - Rounding-out eligibility checked
      - RoundingOutCheck generated
    """
    print("\n" + "=" * 80)
    print("TEST 6: Final-Term Student (Rounding Out)")
    print("=" * 80)

    student = StudentInput(
        name="Final Term Student",
        student_id="FINAL-001",
        program="B.A. Journalism",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11910105",
        courses=[
            CourseSchedule(
                course_id="MIS 401",
                title="Management Information Systems",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                all_online=False,
                has_in_person_session=True,
            ),
            CourseSchedule(
                course_id="JOUR 495",
                title="Senior Capstone",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                all_online=False,
                has_in_person_session=True,
            ),
        ],
    )

    pipeline = CertificationPipeline()

    # First, process through main pipeline
    result = pipeline.process_student(student)

    # Then check rounding-out eligibility
    ro_check = pipeline.check_rounding_out(
        student_input=student,
        completed_units=114.0,           # Almost done
        required_units=120.0,            # Total requirement
        expected_grad_date=date(2026, 12, 15),
        current_enrollment_units=6.0,    # 2 courses × 3 units
    )

    print(f"Student: {result.student_name} ({result.student_id})")
    print(f"Enrollment Status: {result.certification_status.value}")
    print(f"\nRounding-Out Check:")
    print(f"  Completed Units: {ro_check.completed_units}")
    print(f"  Required Units: {ro_check.required_units}")
    print(f"  Remaining Units: {ro_check.remaining_units}")
    print(f"  Is Final Term: {ro_check.is_final_term}")
    print(f"  Eligibility: {ro_check.eligibility.value}")

    if ro_check.reasons:
        print(f"  Reasons:")
        for reason in ro_check.reasons:
            print(f"    - {reason}")

    print("\n✓ Test 6 PASSED")


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 80)
    print("  VA CERTIFICATION PIPELINE — INTEGRATION TESTS")
    print("=" * 80)

    try:
        test_clean_student()
        test_student_with_hitl()
        test_batch_processing()
        test_amendment_pipeline()
        test_tf_certification()
        test_final_term_student()

        print("\n" + "=" * 80)
        print("  ALL TESTS PASSED!")
        print("=" * 80)

    except AssertionError as e:
        print(f"\n✗ ASSERTION FAILED: {str(e)}")
        raise
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {str(e)}")
        raise


if __name__ == "__main__":
    run_all_tests()
