"""
SCO Dashboard for VA Certification Automation — Flask Backend
=============================================================
Serves the React dashboard frontend and provides API endpoints for
managing student certifications, HITL reviews, and amendments.

Sample data: 6 students across SDSU/CSUN with mixed chapters and scenarios.
"""

from flask import Flask, jsonify, request
from datetime import datetime, date, timedelta
import json
from typing import Dict, List, Optional

from decision_tree import (
    StudentInput, CourseSchedule, DecisionTreeOutput, CourseResult,
    run_decision_tree, AcademicLevel, Modality, GradingBasis, TrainingTime,
    CourseExclReason
)
from em_integration import format_for_em, EMEnrollment, SubmissionStatus, HITLReason
from enrollment_monitor import (
    EnrollmentSnapshot, EnrolledCourse, CourseEnrollmentStatus,
    detect_changes, generate_amendment, AmendmentRecord, AmendmentReason,
    ChangeType
)
from weams_programs import match_weams_program, INSTITUTION_REGISTRY

app = Flask(__name__)

# In-memory storage
students_db: Dict = {}
amendments_db: Dict = {}
action_log: List = []

# ============================================================================
# SAMPLE DATA GENERATION
# ============================================================================

def build_sample_students():
    """Create 6 realistic demo students and run them through the full pipeline."""

    students = {}
    now = datetime.now()

    # 1. DANIEL BAHENA — B.A. Journalism, Ch.33, SDSU. Clean certification.
    daniel = StudentInput(
        name="Daniel Bahena",
        student_id="SID-001",
        program="B.A. Journalism",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11910105",  # SDSU
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
                course_id="JOUR 400",
                title="Ethics in Journalism",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="COMM 200",
                title="Communication Theory",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
        ],
    )
    dt_output = run_decision_tree(daniel)
    em_enrollment = format_for_em(
        dt_output,
        student_va_id="001001001",
        student_dob=date(1995, 3, 15),
        facility_code="11910105",
    )
    students["SID-001"] = {
        "student_input": daniel,
        "dt_output": dt_output,
        "em_enrollment": em_enrollment,
        "status": "certified",
        "institution": "SDSU",
        "chapter": "33",
        "created_at": now,
    }

    # 2. MARIA GARCIA — B.S. Computer Science, Ch.35, SDSU. Kitchen sink: audit + repeat + remedial.
    maria = StudentInput(
        name="Maria Garcia",
        student_id="SID-002",
        program="B.S. Computer Science",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch35",
        term="Fall 2026",
        facility_code="11910105",  # SDSU
        courses=[
            CourseSchedule(
                course_id="CS 301",
                title="Data Structures",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="CS 310",
                title="Database Systems",
                units=4.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="MATH 150",
                title="Calculus Review (Audit)",
                units=0.0,
                grading_basis=GradingBasis.AUDIT,
                in_dars=False,
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="CS 250",
                title="Intro to Programming (repeat)",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
                previously_passed=True,
                repeat_exception=False,  # No exception — needs SCO review
            ),
            CourseSchedule(
                course_id="PHIL 332",
                title="Ethics in Technology (substitution)",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=False,  # Not in DARS — pending substitution approval
                has_in_person_session=True,
                all_online=False,
                has_sco_exception=True,
                sco_exception_type="course_substitution",
            ),
        ],
    )
    dt_output = run_decision_tree(maria)
    em_enrollment = format_for_em(
        dt_output,
        student_va_id="002002002",
        student_dob=date(1997, 7, 22),
        facility_code="11910105",
    )
    students["SID-002"] = {
        "student_input": maria,
        "dt_output": dt_output,
        "em_enrollment": em_enrollment,
        "status": "pending_review",  # 2 HITL flags
        "institution": "SDSU",
        "chapter": "35",
        "created_at": now - timedelta(days=2),
    }

    # 3. JAMES CHEN — M.C.P. City Planning, Ch.33, SDSU. Grad with thesis.
    james = StudentInput(
        name="James Chen",
        student_id="SID-003",
        program="M.C.P. City Planning",
        academic_level=AcademicLevel.MASTERS,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11910105",  # SDSU
        enrolled_in_799a=True,  # Thesis
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
                course_id="CP 799A",
                title="Thesis",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=False,
                all_online=True,  # Thesis work is distance
            ),
        ],
    )
    dt_output = run_decision_tree(james)
    em_enrollment = format_for_em(
        dt_output,
        student_va_id="003003003",
        student_dob=date(1994, 11, 8),
        facility_code="11910105",
    )
    students["SID-003"] = {
        "student_input": james,
        "dt_output": dt_output,
        "em_enrollment": em_enrollment,
        "status": "certified",
        "institution": "SDSU",
        "chapter": "33",
        "created_at": now - timedelta(days=5),
    }

    # 4. SARAH KIM — B.A. Psychology, Ch.33, CSUN. Clean.
    sarah = StudentInput(
        name="Sarah Kim",
        student_id="SID-004",
        program="B.A. Psychology",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11918105",  # CSUN
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
    dt_output = run_decision_tree(sarah)
    em_enrollment = format_for_em(
        dt_output,
        student_va_id="004004004",
        student_dob=date(1996, 5, 12),
        facility_code="11918105",
    )
    students["SID-004"] = {
        "student_input": sarah,
        "dt_output": dt_output,
        "em_enrollment": em_enrollment,
        "status": "certified",
        "institution": "CSUN",
        "chapter": "33",
        "created_at": now - timedelta(days=3),
    }

    # 5. ROBERT TORRES — B.S. Civil Engineering, Ch.31, CSUN. Has a pending amendment.
    robert = StudentInput(
        name="Robert Torres",
        student_id="SID-005",
        program="B.S. Civil Engineering",
        academic_level=AcademicLevel.UNDERGRADUATE,
        benefit_chapter="ch31",
        term="Fall 2026",
        facility_code="11918105",  # CSUN
        courses=[
            CourseSchedule(
                course_id="CE 310",
                title="Structural Analysis",
                units=4.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="CE 330",
                title="Hydraulics and Water Resources",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="CE 410",
                title="Transportation Engineering",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
        ],
    )
    dt_output = run_decision_tree(robert)
    em_enrollment = format_for_em(
        dt_output,
        student_va_id="005005005",
        student_dob=date(1993, 9, 30),
        facility_code="11918105",
    )
    students["SID-005"] = {
        "student_input": robert,
        "dt_output": dt_output,
        "em_enrollment": em_enrollment,
        "status": "amendment_pending",  # Dropped a course → pending amendment
        "institution": "CSUN",
        "chapter": "31",
        "created_at": now - timedelta(days=1),
    }

    # 6. LISA NGUYEN — M.A. Comparative Literature, Ch.33, CSUN. Low WEAMS confidence.
    lisa = StudentInput(
        name="Lisa Nguyen",
        student_id="SID-006",
        program="M.A. Comparative World Literature",
        academic_level=AcademicLevel.MASTERS,
        benefit_chapter="ch33",
        term="Fall 2026",
        facility_code="11918105",  # CSUN
        courses=[
            CourseSchedule(
                course_id="ENG 501",
                title="American Literature Seminar",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="ENG 520",
                title="Literary Theory",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=True,
                all_online=False,
            ),
            CourseSchedule(
                course_id="ENG 540",
                title="British Literature Research",
                units=3.0,
                grading_basis=GradingBasis.LETTER,
                in_dars=True,
                dars_rationale="major requirement",
                has_in_person_session=False,
                all_online=True,
            ),
        ],
    )
    dt_output = run_decision_tree(lisa)
    em_enrollment = format_for_em(
        dt_output,
        student_va_id="006006006",
        student_dob=date(1998, 2, 18),
        facility_code="11918105",
        weams_confidence=0.82,  # MEDIUM match → triggers HITL review
    )
    students["SID-006"] = {
        "student_input": lisa,
        "dt_output": dt_output,
        "em_enrollment": em_enrollment,
        "status": "pending_review",  # Low WEAMS confidence → HITL flag
        "institution": "CSUN",
        "chapter": "33",
        "created_at": now - timedelta(days=4),
    }

    return students


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route("/", methods=["GET"])
def serve_dashboard():
    """Serve the React dashboard HTML."""
    with open("dashboard.html", "r") as f:
        return f.read()


@app.route("/api/dashboard", methods=["GET"])
def get_dashboard_summary():
    """
    GET /api/dashboard
    Returns summary statistics for the dashboard header.
    """
    total_students = len(students_db)
    certified = sum(1 for s in students_db.values() if s["status"] == "certified")
    pending_review = sum(1 for s in students_db.values() if s["status"] == "pending_review")
    amendment_pending = sum(1 for s in students_db.values() if s["status"] == "amendment_pending")

    # Count by chapter
    by_chapter = {}
    for student in students_db.values():
        ch = student["chapter"]
        by_chapter[ch] = by_chapter.get(ch, 0) + 1

    # Count by institution
    by_institution = {}
    for student in students_db.values():
        inst = student["institution"]
        by_institution[inst] = by_institution.get(inst, 0) + 1

    return jsonify({
        "total_students": total_students,
        "certified": certified,
        "pending_review": pending_review,
        "amendment_pending": amendment_pending,
        "by_chapter": by_chapter,
        "by_institution": by_institution,
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/students", methods=["GET"])
def get_students_list():
    """
    GET /api/students
    Returns a list of all students with status summaries.
    """
    students_list = []
    for sid, data in students_db.items():
        student_input = data["student_input"]
        dt_output = data["dt_output"]
        students_list.append({
            "id": sid,
            "name": student_input.name,
            "program": student_input.program,
            "chapter": data["chapter"],
            "institution": data["institution"],
            "status": data["status"],
            "certifiable_units": dt_output.total_certifiable_units,
            "residential_units": dt_output.residential_units,
            "distance_units": dt_output.distance_units,
            "training_time": dt_output.training_time.value if dt_output.training_time else None,
            "sco_queue_count": len(dt_output.sco_queue_items or []),
        })

    return jsonify(sorted(students_list, key=lambda x: x["name"]))


@app.route("/api/students/<student_id>", methods=["GET"])
def get_student_detail(student_id):
    """
    GET /api/students/<student_id>
    Returns full detail: decision tree results, EM fields, HITL flags, amendments.
    """
    if student_id not in students_db:
        return jsonify({"error": "Student not found"}), 404

    data = students_db[student_id]
    student_input = data["student_input"]
    dt_output = data["dt_output"]
    em_enrollment = data["em_enrollment"]

    # Build course detail table
    courses = []
    for course_result in dt_output.course_results:
        courses.append({
            "course_id": course_result.course_id,
            "title": course_result.title,
            "units": course_result.units,
            "certifiable": course_result.certifiable,
            "modality": course_result.modality.value if course_result.modality else None,
            "exclusion_reason": course_result.exclusion_reason.value if course_result.exclusion_reason else None,
            "exclusion_detail": course_result.exclusion_detail,
            "flags": course_result.flags,
        })

    # Build HITL flags
    hitl_flags = []
    if em_enrollment.hitl_reasons:
        for reason in em_enrollment.hitl_reasons:
            hitl_flags.append({
                "code": reason.value if isinstance(reason, HITLReason) else reason,
                "description": reason.value if isinstance(reason, HITLReason) else reason,
            })

    # Get amendments for this student
    student_amendments = [a for a in amendments_db.values() if a["student_id"] == student_id]

    return jsonify({
        "id": student_id,
        "name": student_input.name,
        "student_id": student_input.student_id,
        "program": student_input.program,
        "chapter": data["chapter"],
        "institution": data["institution"],
        "status": data["status"],
        "dt_output": {
            "weams_matched": dt_output.weams_matched,
            "weams_program": dt_output.weams_program,
            "total_enrolled_units": dt_output.total_enrolled_units,
            "total_certifiable_units": dt_output.total_certifiable_units,
            "residential_units": dt_output.residential_units,
            "distance_units": dt_output.distance_units,
            "training_time": dt_output.training_time.value if dt_output.training_time else None,
            "rate_of_pursuit": dt_output.rate_of_pursuit,
            "courses": courses,
            "sco_queue_items": [
                {
                    "course_id": item.course_id,
                    "title": item.title,
                    "units": item.units,
                    "exclusion_reason": item.exclusion_reason.value if item.exclusion_reason else None,
                    "exclusion_detail": item.exclusion_detail,
                    "flags": item.flags,
                }
                for item in (dt_output.sco_queue_items or [])
            ],
        },
        "em_enrollment": {
            "status": em_enrollment.status.value,
            "confidence_score": em_enrollment.confidence_score,
            "training_time": em_enrollment.training_time,
            "rate_of_pursuit": em_enrollment.rate_of_pursuit,
            "resident_credits": em_enrollment.resident_credits,
            "distance_credits": em_enrollment.distance_credits,
        },
        "hitl_flags": hitl_flags,
        "amendments": student_amendments,
    })


@app.route("/api/students/<student_id>/approve", methods=["POST"])
def approve_student(student_id):
    """
    POST /api/students/<student_id>/approve
    SCO approves a flagged enrollment (moves from pending_review → certified).
    """
    if student_id not in students_db:
        return jsonify({"error": "Student not found"}), 404

    students_db[student_id]["status"] = "certified"

    action_log.append({
        "timestamp": datetime.now().isoformat(),
        "action": "approve",
        "student_id": student_id,
        "student_name": students_db[student_id]["student_input"].name,
    })

    return jsonify({"status": "approved", "student_id": student_id})


@app.route("/api/students/<student_id>/certify-all", methods=["POST"])
def certify_all(student_id):
    """
    POST /api/students/<student_id>/certify-all
    Batch certify all clean enrollments.
    """
    certified_count = 0
    for sid, data in students_db.items():
        if data["status"] in ["pending_review", "amendment_pending"]:
            # Only certify if no SCO queue items
            if not data["dt_output"].sco_queue_items:
                data["status"] = "certified"
                certified_count += 1
                action_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "action": "batch_certify",
                    "student_id": sid,
                    "student_name": data["student_input"].name,
                })

    return jsonify({
        "action": "batch_certify",
        "certified_count": certified_count,
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/amendments", methods=["GET"])
def get_amendments():
    """
    GET /api/amendments
    List of pending amendments with deltas.
    """
    amendments_list = []
    for aid, amendment in amendments_db.items():
        amendments_list.append({
            "id": aid,
            "student_id": amendment["student_id"],
            "student_name": amendment["student_name"],
            "change_type": amendment.get("change_type", "unknown"),
            "reason": amendment.get("reason", ""),
            "status": amendment.get("status", "pending"),
            "delta": amendment.get("delta", {}),
            "created_at": amendment.get("created_at", ""),
        })

    return jsonify(amendments_list)


@app.route("/api/amendments/<amendment_id>/approve", methods=["POST"])
def approve_amendment(amendment_id):
    """
    POST /api/amendments/<amendment_id>/approve
    SCO approves a pending amendment.
    """
    if amendment_id not in amendments_db:
        return jsonify({"error": "Amendment not found"}), 404

    amendments_db[amendment_id]["status"] = "approved"

    action_log.append({
        "timestamp": datetime.now().isoformat(),
        "action": "approve_amendment",
        "amendment_id": amendment_id,
        "student_name": amendments_db[amendment_id]["student_name"],
    })

    return jsonify({"status": "approved", "amendment_id": amendment_id})


@app.route("/api/audit-log", methods=["GET"])
def get_audit_log():
    """
    GET /api/audit-log
    Timeline of all actions taken in the session.
    """
    return jsonify(sorted(action_log, key=lambda x: x["timestamp"], reverse=True))


# ============================================================================
# INITIALIZATION
# ============================================================================

def init_app():
    """Initialize the app with sample data."""
    global students_db, amendments_db

    students_db = build_sample_students()

    # Create a sample amendment for Robert Torres (dropped CE 410)
    robert_data = students_db["SID-005"]

    # Simulate an old snapshot and a new snapshot with a dropped course
    old_snapshot = EnrollmentSnapshot(
        student_id="SID-005",
        facility_code="11918105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 8, 25, 10, 0, 0),
        courses=[
            EnrolledCourse(
                course_id="CE 310",
                title="Structural Analysis",
                units=4.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="CE 330",
                title="Hydraulics and Water Resources",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="CE 410",
                title="Transportation Engineering",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
        ],
        last_certified=robert_data["dt_output"],
    )

    new_snapshot = EnrollmentSnapshot(
        student_id="SID-005",
        facility_code="11918105",
        term="Fall 2026",
        snapshot_timestamp=datetime(2026, 9, 10, 14, 0, 0),
        courses=[
            EnrolledCourse(
                course_id="CE 310",
                title="Structural Analysis",
                units=4.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            EnrolledCourse(
                course_id="CE 330",
                title="Hydraulics and Water Resources",
                units=3.0,
                modality=Modality.RESIDENTIAL,
                status=CourseEnrollmentStatus.ENROLLED,
            ),
            # CE 410 is dropped
        ],
        last_certified=robert_data["dt_output"],
    )

    changes = detect_changes(old_snapshot, new_snapshot)
    for change in changes:
        if change.requires_amendment:
            amendment = generate_amendment(change, old_snapshot, new_snapshot, robert_data["student_input"])
            if amendment:
                amendment_id = f"AMD-{len(amendments_db) + 1:03d}"
                amendments_db[amendment_id] = {
                    "id": amendment_id,
                    "student_id": "SID-005",
                    "student_name": "Robert Torres",
                    "change_type": change.change_type.value,
                    "reason": amendment.reason.value,
                    "status": "pending",
                    "delta": amendment.delta,
                    "created_at": datetime.now().isoformat(),
                }

    action_log.append({
        "timestamp": datetime.now().isoformat(),
        "action": "app_startup",
        "message": "Dashboard initialized with 6 sample students",
    })


if __name__ == "__main__":
    init_app()
    app.run(debug=True, port=5000)
