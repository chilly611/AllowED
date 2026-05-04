"""
PeopleSoft Adapter Layer — VA Certification Data Bridge
========================================================
Provides an abstract interface for the VA certification pipeline to work with
either real PeopleSoft data (via Oracle) or synthetic data (from Supabase).

The adapter pattern allows the pipeline to remain agnostic to the data source,
and new implementations (e.g., direct Oracle queries) can be added without
modifying the pipeline code.

Architecture:
  1. PeopleSoftAdapter (abstract base class)
  2. MockPeopleSoftAdapter (Supabase + in-memory fallback)
  3. OraclePeopleSoftAdapter (skeleton for future Oracle integration)
  4. Helper functions to convert adapter output to pipeline dataclasses

Authority: Phase 3 Integration (2026-04-18)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Dict, Any


# ---------------------------------------------------------------------------
# Data Classes — PeopleSoft-Native Structures
# ---------------------------------------------------------------------------

@dataclass
class PSStudent:
    """A student record from PeopleSoft."""
    student_id: str              # internal school ID (STUDENT_ID)
    emplid: str                  # VA identifier / Employee ID
    first_name: str
    last_name: str
    dob: date
    email: Optional[str]
    benefit_chapter: str         # 'ch33', 'ch35', 'ch31', etc.
    program: str                 # e.g. "B.A. Journalism"
    academic_level: str          # 'undergraduate', 'masters', 'doctoral'
    facility_code: str           # VA Facility Code
    expected_graduation: Optional[date] = None


@dataclass
class PSCourse:
    """A course from a student's term schedule in PeopleSoft."""
    course_id: str               # e.g. "MIS 401"
    title: str                   # e.g. "Management Information Systems"
    units: float                 # credit units
    grading_basis: str           # 'letter', 'audit', 'pass_fail', 'cr_nc'
    in_dars: bool                # course required for degree per DARS
    dars_rationale: Optional[str] # "major requirement", "GE area", etc.
    has_in_person_session: bool  # at least one required 50+ min in-person
    all_online: bool             # 100% online delivery
    is_remedial: bool            # remedial/developmental course
    is_repeat: bool              # student is retaking this course
    previously_passed: bool      # for repeat detection logic
    is_thesis: bool              # thesis/capstone designation
    is_practicum: bool           # practicum/internship = always residential
    pre_term_only: bool          # in-person sessions only before term starts


@dataclass
class PSTuition:
    """Tuition and fees record from bursar."""
    gross_tuition: float         # total tuition before aid
    aid_amount: float            # aid applied
    net_tuition: float           # gross - aid (for Ch.33 certification)
    fees: float                  # non-instructional fees


@dataclass
class PSEnrollmentSnapshot:
    """Complete enrollment state for a student in a term."""
    student_id: str
    term: str
    courses: List[PSCourse]
    program: str
    graduated: bool
    snapshot_timestamp: datetime


# ---------------------------------------------------------------------------
# Abstract Base Class
# ---------------------------------------------------------------------------

class PeopleSoftAdapter(ABC):
    """
    Abstract interface for accessing student data from PeopleSoft.

    Implementations should provide access to:
      - Student demographic and enrollment data
      - Course schedules with modality info
      - DARS applicability data
      - Tuition and fees from bursar
      - Enrollment change history
    """

    @abstractmethod
    def get_student(self, student_id: str) -> PSStudent:
        """
        Retrieve a student record by internal ID.

        Args:
            student_id: Internal student ID (not EMPLID)

        Returns:
            PSStudent with full demographic and enrollment info

        Raises:
            ValueError: if student_id not found
        """
        pass

    @abstractmethod
    def get_enrollment_snapshot(self, student_id: str, term: str) -> PSEnrollmentSnapshot:
        """
        Get a snapshot of a student's enrollment for a specific term.

        Args:
            student_id: Internal student ID
            term: Term code or name (e.g. "Fall 2024", "SP2024")

        Returns:
            PSEnrollmentSnapshot with all enrolled courses

        Raises:
            ValueError: if student_id or term not found
        """
        pass

    @abstractmethod
    def get_course_schedule(self, student_id: str, term: str) -> List[PSCourse]:
        """
        Get the list of courses a student is enrolled in for a term.

        Args:
            student_id: Internal student ID
            term: Term code or name

        Returns:
            List of PSCourse objects with modality and DARS data

        Raises:
            ValueError: if student_id or term not found
        """
        pass

    @abstractmethod
    def get_tuition(self, student_id: str, term: str) -> PSTuition:
        """
        Retrieve tuition and fees for a student in a term.

        Data comes from bursar/student accounts system.

        Args:
            student_id: Internal student ID
            term: Term code or name

        Returns:
            PSTuition with gross, aid, net, and fees amounts

        Raises:
            ValueError: if student_id or term not found
        """
        pass

    @abstractmethod
    def list_students_for_term(self, facility_code: str, term: str) -> List[PSStudent]:
        """
        List all students for a facility/term (for batch processing).

        Args:
            facility_code: VA Facility Code (e.g. "11910105" for SDSU)
            term: Term code or name

        Returns:
            List of PSStudent objects enrolled in the term

        Raises:
            ValueError: if facility_code or term invalid
        """
        pass

    @abstractmethod
    def get_enrollment_changes(self, facility_code: str, since: datetime) -> List[Dict[str, Any]]:
        """
        Get list of enrollment changes since a given timestamp.

        Used by the amendment engine to detect drops, adds, withdrawals.

        Args:
            facility_code: VA Facility Code
            since: Only return changes after this timestamp

        Returns:
            List of change dictionaries with keys:
              - student_id
              - term
              - change_type: 'add', 'drop', 'withdrawal', 'grade_change'
              - course_id
              - timestamp

        Raises:
            ValueError: if facility_code invalid
        """
        pass

    @abstractmethod
    def get_dars_remaining_units(self, student_id: str) -> float:
        """
        Get the number of remaining units a student needs per DARS.

        Used for rounding-out eligibility checks in final term.

        Args:
            student_id: Internal student ID

        Returns:
            Remaining units to complete degree (0.0 if completed)

        Raises:
            ValueError: if student_id not found
        """
        pass


# ---------------------------------------------------------------------------
# MockPeopleSoftAdapter — Supabase + In-Memory Fallback
# ---------------------------------------------------------------------------

class MockPeopleSoftAdapter(PeopleSoftAdapter):
    """
    Test implementation using in-memory data or Supabase tables.

    Can be initialized three ways:
      1. From Supabase (live data): MockPeopleSoftAdapter(supabase_url, supabase_key)
      2. From dict (test data): MockPeopleSoftAdapter.from_dict(data_dict)
      3. With fallback: tries Supabase first, falls back to in-memory if unavailable

    The fallback in-memory mode ensures backward compatibility with existing
    pipeline tests that don't have Supabase configured.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the adapter.

        Args:
            supabase_url: Supabase project URL (e.g. https://xyz.supabase.co)
            supabase_key: Supabase service role key (full access)
            data: In-memory fallback data (dict with tables as keys)
        """
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.use_supabase = supabase_url and supabase_key
        self.client = None
        self.data = data or {}

        # Attempt Supabase connection if credentials provided
        if self.use_supabase:
            try:
                import supabase as supabase_lib
                self.client = supabase_lib.create_client(supabase_url, supabase_key)
            except Exception as e:
                # Fall back to in-memory
                print(f"Warning: Supabase connection failed ({e}), using in-memory fallback")
                self.use_supabase = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MockPeopleSoftAdapter":
        """
        Create an adapter from a plain dictionary (for testing).

        The dict should have keys like:
          - 'students': list of student dicts
          - 'enrollments': list of enrollment records
          - 'courses': list of course definitions
          - 'tuition_fees': list of tuition records
          - 'dars': list of DARS requirement records

        Args:
            data: Dictionary with table data

        Returns:
            MockPeopleSoftAdapter instance
        """
        return cls(supabase_url=None, supabase_key=None, data=data)

    def get_student(self, student_id: str) -> PSStudent:
        """Retrieve a student from in-memory or Supabase."""
        if self.use_supabase and self.client:
            try:
                response = self.client.table("students").select("*").eq("student_id", student_id).execute()
                if response.data:
                    return self._dict_to_ps_student(response.data[0])
            except Exception:
                pass

        # Fall back to in-memory
        students = self.data.get("students", [])
        for s in students:
            if s.get("student_id") == student_id:
                return self._dict_to_ps_student(s)

        raise ValueError(f"Student {student_id} not found")

    def get_enrollment_snapshot(self, student_id: str, term: str) -> PSEnrollmentSnapshot:
        """Get enrollment snapshot from in-memory or Supabase."""
        courses = self.get_course_schedule(student_id, term)
        try:
            student = self.get_student(student_id)
        except ValueError:
            raise ValueError(f"Student {student_id} not found")

        return PSEnrollmentSnapshot(
            student_id=student_id,
            term=term,
            courses=courses,
            program=student.program,
            graduated=False,
            snapshot_timestamp=datetime.now(),
        )

    def get_course_schedule(self, student_id: str, term: str) -> List[PSCourse]:
        """Get course schedule from in-memory or Supabase."""
        if self.use_supabase and self.client:
            try:
                response = (
                    self.client.table("course_schedules")
                    .select("*")
                    .eq("student_id", student_id)
                    .eq("term", term)
                    .execute()
                )
                if response.data:
                    return [self._dict_to_ps_course(c) for c in response.data]
            except Exception:
                pass

        # Fall back to in-memory
        schedules = self.data.get("course_schedules", [])
        courses = []
        for s in schedules:
            if s.get("student_id") == student_id and s.get("term") == term:
                courses.append(self._dict_to_ps_course(s))

        return courses

    def get_tuition(self, student_id: str, term: str) -> PSTuition:
        """Get tuition and fees from in-memory or Supabase."""
        if self.use_supabase and self.client:
            try:
                response = (
                    self.client.table("tuition_fees_records")
                    .select("*")
                    .eq("student_id", student_id)
                    .eq("term", term)
                    .execute()
                )
                if response.data:
                    return self._dict_to_ps_tuition(response.data[0])
            except Exception:
                pass

        # Fall back to in-memory
        records = self.data.get("tuition_fees_records", [])
        for r in records:
            if r.get("student_id") == student_id and r.get("term") == term:
                return self._dict_to_ps_tuition(r)

        raise ValueError(f"Tuition record for {student_id}/{term} not found")

    def list_students_for_term(self, facility_code: str, term: str) -> List[PSStudent]:
        """List all students for a facility/term from in-memory or Supabase."""
        if self.use_supabase and self.client:
            try:
                response = (
                    self.client.table("students")
                    .select("*")
                    .eq("facility_code", facility_code)
                    .execute()
                )
                if response.data:
                    return [self._dict_to_ps_student(s) for s in response.data]
            except Exception:
                pass

        # Fall back to in-memory
        students = self.data.get("students", [])
        result = []
        for s in students:
            if s.get("facility_code") == facility_code:
                result.append(self._dict_to_ps_student(s))
        return result

    def get_enrollment_changes(self, facility_code: str, since: datetime) -> List[Dict[str, Any]]:
        """Get enrollment changes since a timestamp from in-memory or Supabase."""
        if self.use_supabase and self.client:
            try:
                response = (
                    self.client.table("enrollment_changes")
                    .select("*")
                    .gte("timestamp", since.isoformat())
                    .execute()
                )
                if response.data:
                    return response.data
            except Exception:
                pass

        # Fall back to in-memory
        changes = self.data.get("enrollment_changes", [])
        result = []
        for c in changes:
            ts = c.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            if ts >= since:
                result.append(c)
        return result

    def get_dars_remaining_units(self, student_id: str) -> float:
        """Get DARS remaining units from in-memory or Supabase."""
        if self.use_supabase and self.client:
            try:
                response = (
                    self.client.table("dars_requirements")
                    .select("remaining_units")
                    .eq("student_id", student_id)
                    .execute()
                )
                if response.data:
                    return float(response.data[0].get("remaining_units", 0.0))
            except Exception:
                pass

        # Fall back to in-memory
        dars = self.data.get("dars_requirements", [])
        for d in dars:
            if d.get("student_id") == student_id:
                return float(d.get("remaining_units", 0.0))

        return 0.0

    # -----------------------------------------------------------------------
    # Private conversion helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _dict_to_ps_student(data: Dict[str, Any]) -> PSStudent:
        """Convert dict to PSStudent."""
        dob = data.get("dob")
        if isinstance(dob, str):
            dob = date.fromisoformat(dob)

        expected_grad = data.get("expected_graduation")
        if isinstance(expected_grad, str):
            expected_grad = date.fromisoformat(expected_grad)

        return PSStudent(
            student_id=data.get("student_id", ""),
            emplid=data.get("emplid", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            dob=dob,
            email=data.get("email"),
            benefit_chapter=data.get("benefit_chapter", "ch33"),
            program=data.get("program", ""),
            academic_level=data.get("academic_level", "undergraduate"),
            facility_code=data.get("facility_code", "11910105"),
            expected_graduation=expected_grad,
        )

    @staticmethod
    def _dict_to_ps_course(data: Dict[str, Any]) -> PSCourse:
        """Convert dict to PSCourse."""
        return PSCourse(
            course_id=data.get("course_id", ""),
            title=data.get("title", ""),
            units=float(data.get("units", 0.0)),
            grading_basis=data.get("grading_basis", "letter"),
            in_dars=data.get("in_dars", False),
            dars_rationale=data.get("dars_rationale"),
            has_in_person_session=data.get("has_in_person_session", False),
            all_online=data.get("all_online", False),
            is_remedial=data.get("is_remedial", False),
            is_repeat=data.get("is_repeat", False),
            previously_passed=data.get("previously_passed", False),
            is_thesis=data.get("is_thesis", False),
            is_practicum=data.get("is_practicum", False),
            pre_term_only=data.get("pre_term_only", False),
        )

    @staticmethod
    def _dict_to_ps_tuition(data: Dict[str, Any]) -> PSTuition:
        """Convert dict to PSTuition."""
        return PSTuition(
            gross_tuition=float(data.get("gross_tuition", 0.0)),
            aid_amount=float(data.get("aid_amount", 0.0)),
            net_tuition=float(data.get("net_tuition", 0.0)),
            fees=float(data.get("fees", 0.0)),
        )


# ---------------------------------------------------------------------------
# OraclePeopleSoftAdapter — Skeleton for Future Implementation
# ---------------------------------------------------------------------------

class OraclePeopleSoftAdapter(PeopleSoftAdapter):
    """
    Skeleton implementation for direct Oracle PeopleSoft database access.

    Every method raises NotImplementedError with hints for the Oracle table
    that should be queried. Replace with cx_Oracle queries when ready.

    Expected setup:
      - cx_Oracle client configured
      - Oracle connection string (host, port, service name)
      - Database credentials from secure storage (not hardcoded)
    """

    def __init__(self, connection_string: str):
        """
        Initialize Oracle adapter.

        Args:
            connection_string: Oracle DSN or connection URL
                Example: "user/password@host:1521/SERVICE_NAME"

        Note: Credentials should come from environment variables or vaults,
              never hardcoded.
        """
        self.connection_string = connection_string
        self.connection = None
        # TODO: Initialize cx_Oracle connection

    def get_student(self, student_id: str) -> PSStudent:
        """
        Query: SELECT EMPLID, NAME, BIRTHDATE FROM SCC_PERDATA_QVW WHERE EMPLID = :emplid

        Also join with:
          - STDNT_CAREER for academic_level, program
          - PERSONAL_DATA for email, address
        """
        raise NotImplementedError(
            "OraclePeopleSoftAdapter.get_student() not implemented. "
            "Wire to cx_Oracle query: "
            "SELECT EMPLID, NAME, BIRTHDATE FROM SCC_PERDATA_QVW WHERE EMPLID = :emplid"
        )

    def get_enrollment_snapshot(self, student_id: str, term: str) -> PSEnrollmentSnapshot:
        """
        Query STDNT_ENRL table for enrollment records + course details.

        Joins:
          - STDNT_ENRL: student enrollment
          - CLASS_TBL: course definitions
          - TERM_TBL: term metadata
        """
        raise NotImplementedError(
            "OraclePeopleSoftAdapter.get_enrollment_snapshot() not implemented. "
            "Wire to cx_Oracle query: "
            "SELECT * FROM STDNT_ENRL WHERE STUDENT_ID = :sid AND TERM = :term"
        )

    def get_course_schedule(self, student_id: str, term: str) -> List[PSCourse]:
        """
        Query: SELECT course details FROM STDNT_ENRL WHERE STUDENT_ID = :sid AND TERM = :term

        Joins:
          - SSR_VB_INSTR_MAP: delivery method (in-person, online, hybrid)
          - CLASS_SECTION: meeting times and locations
          - SAA_DEGREE_AUDIT: DARS applicability
        """
        raise NotImplementedError(
            "OraclePeopleSoftAdapter.get_course_schedule() not implemented. "
            "Wire to cx_Oracle query: "
            "SELECT * FROM STDNT_ENRL WHERE STUDENT_ID = :sid AND TERM = :term"
        )

    def get_tuition(self, student_id: str, term: str) -> PSTuition:
        """
        Query: SELECT tuition amounts FROM SSR_VB_TUI_WRK_FED (net) + TUITION_CALC_TBL (gross)

        Also join with:
          - FINANCIAL_AID: aid amounts
          - ITEM_FEES: fee amounts
        """
        raise NotImplementedError(
            "OraclePeopleSoftAdapter.get_tuition() not implemented. "
            "Wire to cx_Oracle query: "
            "SELECT NET_TUITION FROM SSR_VB_TUI_WRK_FED WHERE STUDENT_ID = :sid AND TERM = :term"
        )

    def list_students_for_term(self, facility_code: str, term: str) -> List[PSStudent]:
        """
        Query: SELECT * FROM SSR_VB_DATA WHERE FACILITY_ID = :code AND TERM = :term

        Joins with student demographic tables for bulk enrollment certification.
        """
        raise NotImplementedError(
            "OraclePeopleSoftAdapter.list_students_for_term() not implemented. "
            "Wire to cx_Oracle query: "
            "SELECT * FROM SSR_VB_DATA WHERE FACILITY_ID = :code AND TERM = :term"
        )

    def get_enrollment_changes(self, facility_code: str, since: datetime) -> List[Dict[str, Any]]:
        """
        Query: SELECT * FROM STDNT_ENRL WHERE LAST_UPD_DT_STMP >= :since

        Filters to detect drops, adds, withdrawals for the amendment engine.
        """
        raise NotImplementedError(
            "OraclePeopleSoftAdapter.get_enrollment_changes() not implemented. "
            "Wire to cx_Oracle query: "
            "SELECT * FROM STDNT_ENRL WHERE LAST_UPD_DT_STMP >= :since"
        )

    def get_dars_remaining_units(self, student_id: str) -> float:
        """
        Query: SELECT remaining_units FROM SAA_RPT_RQST WHERE STUDENT_ID = :sid

        Used for rounding-out eligibility in final term.
        """
        raise NotImplementedError(
            "OraclePeopleSoftAdapter.get_dars_remaining_units() not implemented. "
            "Wire to cx_Oracle query: "
            "SELECT REMAINING_UNITS FROM SAA_RPT_RQST WHERE STUDENT_ID = :sid"
        )


# ---------------------------------------------------------------------------
# Helper Functions — Convert to Pipeline Dataclasses
# ---------------------------------------------------------------------------

def to_student_input(ps_student: PSStudent, ps_courses: List[PSCourse], term: str) -> 'StudentInput':
    """
    Convert PeopleSoft student + courses to pipeline StudentInput dataclass.

    Args:
        ps_student: PSStudent from adapter
        ps_courses: List of PSCourse from adapter
        term: Term name/code

    Returns:
        StudentInput ready for decision_tree.run_decision_tree()

    Raises:
        ImportError: if decision_tree module not available
    """
    try:
        from decision_tree import StudentInput, AcademicLevel, CourseSchedule, GradingBasis
    except ImportError as e:
        raise ImportError(f"Cannot import decision_tree module: {e}")

    # Map academic level
    academic_level_map = {
        "undergraduate": AcademicLevel.UNDERGRADUATE,
        "masters": AcademicLevel.MASTERS,
        "doctoral": AcademicLevel.DOCTORAL,
    }
    academic_level = academic_level_map.get(ps_student.academic_level, AcademicLevel.UNDERGRADUATE)

    # Convert courses
    courses = []
    for ps_course in ps_courses:
        # Map grading basis
        grading_basis_map = {
            "letter": GradingBasis.LETTER,
            "audit": GradingBasis.AUDIT,
            "pass_fail": GradingBasis.CR_NC,
            "cr_nc": GradingBasis.CR_NC,
        }
        grading_basis = grading_basis_map.get(ps_course.grading_basis, GradingBasis.LETTER)

        course = CourseSchedule(
            course_id=ps_course.course_id,
            title=ps_course.title,
            units=ps_course.units,
            grading_basis=grading_basis,
            is_remedial=ps_course.is_remedial,
            in_dars=ps_course.in_dars,
            dars_rationale=ps_course.dars_rationale or "",
            has_in_person_session=ps_course.has_in_person_session,
            all_online=ps_course.all_online,
            is_pre_term_only=ps_course.pre_term_only,
            is_practicum=ps_course.is_practicum,
            previously_passed=ps_course.previously_passed,
            repeat_exception=False,  # Placeholder; set by SCO review
            has_sco_exception=False,
            sco_exception_type="",
        )
        courses.append(course)

    full_name = f"{ps_student.first_name} {ps_student.last_name}".strip()

    return StudentInput(
        name=full_name,
        student_id=ps_student.student_id,
        program=ps_student.program,
        academic_level=academic_level,
        benefit_chapter=ps_student.benefit_chapter,
        term=term,
        courses=courses,
        facility_code=ps_student.facility_code,
        enrolled_in_799a=False,  # Would be detected from courses
        enrolled_in_897=False,
        enrolled_in_899=False,
    )


def to_course_schedule(ps_course: PSCourse) -> 'CourseSchedule':
    """
    Convert a single PSCourse to pipeline CourseSchedule.

    Args:
        ps_course: PSCourse from adapter

    Returns:
        CourseSchedule ready for decision tree

    Raises:
        ImportError: if decision_tree module not available
    """
    try:
        from decision_tree import CourseSchedule, GradingBasis
    except ImportError as e:
        raise ImportError(f"Cannot import decision_tree module: {e}")

    grading_basis_map = {
        "letter": GradingBasis.LETTER,
        "audit": GradingBasis.AUDIT,
        "pass_fail": GradingBasis.CR_NC,
        "cr_nc": GradingBasis.CR_NC,
    }
    grading_basis = grading_basis_map.get(ps_course.grading_basis, GradingBasis.LETTER)

    return CourseSchedule(
        course_id=ps_course.course_id,
        title=ps_course.title,
        units=ps_course.units,
        grading_basis=grading_basis,
        is_remedial=ps_course.is_remedial,
        in_dars=ps_course.in_dars,
        dars_rationale=ps_course.dars_rationale or "",
        has_in_person_session=ps_course.has_in_person_session,
        all_online=ps_course.all_online,
        is_pre_term_only=ps_course.pre_term_only,
        is_practicum=ps_course.is_practicum,
        previously_passed=ps_course.previously_passed,
        repeat_exception=False,
        has_sco_exception=False,
        sco_exception_type="",
    )
