"""FastAPI application for AllowED VA Certification Automation"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import json
from datetime import datetime, date
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_supabase
from api.auth import get_current_user, require_superadmin
from api.models import (
    DashboardResponse, StudentListItem, StudentDetail, ApproveRequest,
    AmendmentListItem, AuditLogEntry, HITLItem, TFRecord,
    AdminCreateInstitution, AdminCreateUser, AdminUploadWEAMS,
    AdminMetricsResponse, AdminGenerateCohortRequest, PaginatedResponse,
    BatchCertifyRequest, BatchCertifyResponse, ProcessStudentRequest, ProcessStudentResponse,
    ApproveAmendmentRequest
)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger("allowed")

app = FastAPI(
    title="AllowED API",
    description="VA Enrollment Certification Automation",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Catch-all exception handler - no stack traces in production"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Service health check"""
    return {"status": "ok", "service": "AllowED API"}


# ============================================================================
# CORE ROUTES (Institution-scoped)
# ============================================================================

@app.get("/api/dashboard", response_model=DashboardResponse)
async def get_dashboard(user=Depends(get_current_user)):
    """
    Get dashboard overview for authenticated user's institution.
    Returns: total_students, ready_for_batch, hitl_pending, amendments_pending,
             submitted_today, tf_pending
    """
    sb = get_supabase()
    inst_id = user["institution_id"]

    try:
        # Total students
        total_students = sb.table("students").select("id", count="exact").eq("institution_id", inst_id).execute()
        total_count = total_students.count

        # Ready for batch
        ready = sb.table("enrollments").select("id", count="exact").eq("institution_id", inst_id).eq("status", "ready_for_batch").execute()
        ready_count = ready.count

        # HITL pending
        hitl = sb.table("hitl_queue").select("id", count="exact").eq("institution_id", inst_id).eq("status", "open").execute()
        hitl_count = hitl.count

        # Amendments pending
        amendments = sb.table("amendments").select("id", count="exact").eq("institution_id", inst_id).eq("status", "pending_review").execute()
        amend_count = amendments.count

        # Submitted today
        today = date.today().isoformat()
        submitted = sb.table("certifications_submitted").select("id", count="exact").eq("institution_id", inst_id).gte("created_at", f"{today}T00:00:00").execute()
        submitted_count = submitted.count

        # T&F pending
        tf_pending = sb.table("tuition_fees_records").select("id", count="exact").eq("institution_id", inst_id).eq("status", "pending_bursar_report").execute()
        tf_count = tf_pending.count

        return DashboardResponse(
            total_students=total_count,
            ready_for_batch=ready_count,
            hitl_pending=hitl_count,
            amendments_pending=amend_count,
            submitted_today=submitted_count,
            tf_pending=tf_count
        )
    except Exception as e:
        logger.error(f"Dashboard query failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load dashboard")


@app.get("/api/students", response_model=PaginatedResponse)
async def list_students(
    term: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user)
):
    """
    Paginated student list for user's institution.
    Optional filters: term, enrollment status
    """
    sb = get_supabase()
    inst_id = user["institution_id"]

    try:
        query = sb.table("students").select(
            "id, student_id_internal, first_name, last_name, program, benefit_chapter, active"
        ).eq("institution_id", inst_id).eq("active", True)

        # Get total count
        count_response = query.execute()
        total = len(count_response.data)

        # Apply pagination
        offset = (page - 1) * limit
        students_response = sb.table("students").select(
            "id, student_id_internal, first_name, last_name, program, benefit_chapter"
        ).eq("institution_id", inst_id).eq("active", True).range(offset, offset + limit - 1).execute()

        students = []
        for student in students_response.data:
            # Get latest enrollment for status info
            enrollment_response = sb.table("enrollments").select(
                "status, total_certifiable_units, training_time"
            ).eq("student_id", student["id"]).order("created_at", desc=True).limit(1).execute()

            enrollment = enrollment_response.data[0] if enrollment_response.data else {}

            students.append(StudentListItem(
                id=student["id"],
                name=f"{student['first_name']} {student['last_name']}",
                student_id_internal=student["student_id_internal"],
                program=student.get("program"),
                benefit_chapter=student.get("benefit_chapter"),
                enrollment_status=enrollment.get("status", "pending"),
                total_certifiable_units=enrollment.get("total_certifiable_units"),
                training_time=enrollment.get("training_time")
            ))

        has_next = (offset + limit) < total

        return PaginatedResponse(
            items=students,
            total=total,
            page=page,
            limit=limit,
            has_next=has_next
        )
    except Exception as e:
        logger.error(f"Student list query failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load students")


@app.get("/api/students/{student_id}", response_model=StudentDetail)
async def get_student_detail(student_id: int, user=Depends(get_current_user)):
    """
    Get full student detail including enrollment, courses, amendments, HITL items.
    Must verify student belongs to user's institution.
    """
    sb = get_supabase()
    inst_id = user["institution_id"]

    try:
        # Verify student belongs to user's institution
        student_response = sb.table("students").select("*").eq("id", student_id).eq("institution_id", inst_id).single().execute()

        if not student_response.data:
            raise HTTPException(status_code=404, detail="Student not found")

        student = student_response.data

        # Get enrollment
        enrollment_response = sb.table("enrollments").select("*").eq("student_id", student_id).order("created_at", desc=True).limit(1).execute()
        enrollment = enrollment_response.data[0] if enrollment_response.data else None

        # Get courses if enrollment exists
        courses = []
        if enrollment:
            courses_response = sb.table("course_schedules").select("*").eq("enrollment_id", enrollment["id"]).execute()
            courses = courses_response.data

        # Get amendments
        amendments = []
        if enrollment:
            amend_response = sb.table("amendments").select("*").eq("enrollment_id", enrollment["id"]).execute()
            amendments = amend_response.data

        # Get tuition & fees
        tf = []
        tf_response = sb.table("tuition_fees_records").select("*").eq("student_id", student_id).eq("institution_id", inst_id).execute()
        tf = tf_response.data

        # Get HITL items
        hitl = []
        if enrollment:
            hitl_response = sb.table("hitl_queue").select("*").eq("enrollment_id", enrollment["id"]).execute()
            hitl = hitl_response.data

        return StudentDetail(
            id=student["id"],
            student_id_internal=student["student_id_internal"],
            first_name=student["first_name"],
            last_name=student["last_name"],
            email=student.get("email"),
            dob=student.get("dob"),
            program=student.get("program"),
            benefit_chapter=student.get("benefit_chapter"),
            academic_level=student.get("academic_level"),
            enrollment=enrollment,
            courses=courses,
            amendments=amendments,
            tuition_fees=tf,
            hitl_items=hitl,
            decision_tree_output=enrollment.get("decision_tree_output") if enrollment else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Student detail query failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load student details")


@app.post("/api/students/{student_id}/approve")
async def approve_student(
    student_id: int,
    request: ApproveRequest,
    user=Depends(get_current_user)
):
    """
    Approve HITL item for student. Moves enrollment from hitl_review to ready_for_batch.
    Creates audit log entry.
    """
    sb = get_supabase()
    inst_id = user["institution_id"]
    user_id = user["id"]

    try:
        # Get enrollment
        enrollment_response = sb.table("enrollments").select("*").eq("institution_id", inst_id).eq("status", "hitl_review").eq("student_id", student_id).single().execute()

        if not enrollment_response.data:
            raise HTTPException(status_code=404, detail="No HITL review item found for student")

        enrollment = enrollment_response.data

        # Update enrollment status
        sb.table("enrollments").update({"status": "ready_for_batch", "updated_at": datetime.utcnow().isoformat()}).eq("id", enrollment["id"]).execute()

        # Create audit log
        sb.table("audit_log").insert({
            "institution_id": inst_id,
            "user_id": user_id,
            "action": "approve_hitl",
            "entity_type": "enrollment",
            "entity_id": enrollment["id"],
            "details": {"notes": request.notes}
        }).execute()

        return {"status": "approved", "enrollment_id": enrollment["id"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approve student failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to approve student")


@app.post("/api/students/certify-batch", response_model=BatchCertifyResponse)
async def certify_batch(
    request: BatchCertifyRequest,
    user=Depends(get_current_user)
):
    """
    Run pipeline on batch of students. If student_ids not provided, uses all ready_for_batch.
    Updates status to submitted. Creates audit log entries.
    """
    sb = get_supabase()
    inst_id = user["institution_id"]
    user_id = user["id"]

    try:
        # Get students to certify
        if request.student_ids:
            # Specific students
            enrollments_response = sb.table("enrollments").select("*").eq("institution_id", inst_id).in_("student_id", request.student_ids).execute()
        else:
            # All ready_for_batch
            enrollments_response = sb.table("enrollments").select("*").eq("institution_id", inst_id).eq("status", "ready_for_batch").execute()

        enrollments = enrollments_response.data
        certified_count = 0
        failed_count = 0
        errors = []

        for enrollment in enrollments:
            try:
                # Update status to submitted
                sb.table("enrollments").update({
                    "status": "submitted",
                    "submitted_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", enrollment["id"]).execute()

                # Create submission record
                sb.table("certifications_submitted").insert({
                    "enrollment_id": enrollment["id"],
                    "institution_id": inst_id,
                    "submission_type": "initial",
                    "status": "pending",
                    "submitted_by": user_id
                }).execute()

                # Create audit log
                sb.table("audit_log").insert({
                    "institution_id": inst_id,
                    "user_id": user_id,
                    "action": "batch_certify",
                    "entity_type": "enrollment",
                    "entity_id": enrollment["id"],
                    "details": {}
                }).execute()

                certified_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    "student_id": enrollment["student_id"],
                    "error": str(e)
                })

        return BatchCertifyResponse(
            certified_count=certified_count,
            failed_count=failed_count,
            errors=errors if errors else None
        )
    except Exception as e:
        logger.error(f"Batch certification failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Batch certification failed")


@app.get("/api/amendments", response_model=PaginatedResponse)
async def list_amendments(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user)
):
    """
    List amendments for user's institution with student names.
    Optional status filter.
    """
    sb = get_supabase()
    inst_id = user["institution_id"]

    try:
        query = sb.table("amendments").select("*").eq("institution_id", inst_id)

        if status:
            query = query.eq("status", status)

        # Get total
        result = query.execute()
        total = len(result.data)

        # Paginate
        offset = (page - 1) * limit
        amendments_response = query.range(offset, offset + limit - 1).execute()

        items = []
        for amend in amendments_response.data:
            # Get student name
            student_response = sb.table("students").select("first_name, last_name").eq("id", amend["student_id"]).single().execute()
            student = student_response.data or {"first_name": "Unknown", "last_name": ""}

            items.append(AmendmentListItem(
                id=amend["id"],
                student_name=f"{student['first_name']} {student['last_name']}",
                student_id=amend["student_id"],
                amendment_reason=amend["amendment_reason"],
                status=amend["status"],
                original_data=amend.get("original_data"),
                revised_data=amend.get("revised_data"),
                created_at=amend["created_at"]
            ))

        has_next = (offset + limit) < total
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_next=has_next
        )
    except Exception as e:
        logger.error(f"Amendment list query failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load amendments")


@app.post("/api/amendments/{amendment_id}/approve")
async def approve_amendment(
    amendment_id: int,
    request: ApproveAmendmentRequest,
    user=Depends(get_current_user)
):
    """
    Approve amendment. Updates status and creates audit log.
    """
    sb = get_supabase()
    inst_id = user["institution_id"]
    user_id = user["id"]

    try:
        # Get amendment
        amendment_response = sb.table("amendments").select("*").eq("id", amendment_id).eq("institution_id", inst_id).single().execute()

        if not amendment_response.data:
            raise HTTPException(status_code=404, detail="Amendment not found")

        amendment = amendment_response.data

        # Update amendment
        sb.table("amendments").update({
            "status": "approved",
            "approved_by": user_id,
            "approved_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", amendment_id).execute()

        # Create audit log
        sb.table("audit_log").insert({
            "institution_id": inst_id,
            "user_id": user_id,
            "action": "approve_amendment",
            "entity_type": "amendment",
            "entity_id": amendment_id,
            "details": {"notes": request.notes}
        }).execute()

        return {"status": "approved", "amendment_id": amendment_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approve amendment failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to approve amendment")


@app.get("/api/audit-log", response_model=PaginatedResponse)
async def get_audit_log(
    action: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user)
):
    """
    Paginated audit log for user's institution. Newest first.
    Optional action filter.
    """
    sb = get_supabase()
    inst_id = user["institution_id"]

    try:
        query = sb.table("audit_log").select("*").eq("institution_id", inst_id)

        if action:
            query = query.eq("action", action)

        # Get total
        result = query.execute()
        total = len(result.data)

        # Paginate, order by created_at DESC
        offset = (page - 1) * limit
        logs_response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

        items = []
        for log in logs_response.data:
            # Get user email if available
            user_email = None
            if log.get("user_id"):
                user_response = sb.table("sco_users").select("email").eq("id", log["user_id"]).single().execute()
                if user_response.data:
                    user_email = user_response.data["email"]

            items.append(AuditLogEntry(
                id=log["id"],
                action=log["action"],
                entity_type=log["entity_type"],
                entity_id=log.get("entity_id"),
                user_email=user_email,
                details=log.get("details"),
                created_at=log["created_at"]
            ))

        has_next = (offset + limit) < total
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_next=has_next
        )
    except Exception as e:
        logger.error(f"Audit log query failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load audit log")


@app.get("/api/hitl-queue", response_model=PaginatedResponse)
async def get_hitl_queue(
    priority: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user)
):
    """
    HITL queue items for user's institution.
    Optional filters: priority, status
    """
    sb = get_supabase()
    inst_id = user["institution_id"]

    try:
        query = sb.table("hitl_queue").select("*").eq("institution_id", inst_id)

        if priority:
            query = query.eq("priority", priority)
        if status:
            query = query.eq("status", status)

        # Get total
        result = query.execute()
        total = len(result.data)

        # Paginate
        offset = (page - 1) * limit
        hitl_response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

        items = []
        for item in hitl_response.data:
            # Get student name
            if item.get("enrollment_id"):
                enrollment_response = sb.table("enrollments").select("student_id").eq("id", item["enrollment_id"]).single().execute()
                if enrollment_response.data:
                    student_id = enrollment_response.data["student_id"]
                    student_response = sb.table("students").select("first_name, last_name").eq("id", student_id).single().execute()
                    if student_response.data:
                        student = student_response.data
                        student_name = f"{student['first_name']} {student['last_name']}"
                    else:
                        student_name = "Unknown"
                        student_id = None
                else:
                    student_name = "Unknown"
                    student_id = None
            else:
                student_name = "Unknown"
                student_id = None

            items.append(HITLItem(
                id=item["id"],
                student_name=student_name,
                student_id=student_id or 0,
                flag_type=item["flag_type"],
                flag_reason=item["flag_reason"],
                priority=item["priority"],
                status=item["status"],
                created_at=item["created_at"]
            ))

        has_next = (offset + limit) < total
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_next=has_next
        )
    except Exception as e:
        logger.error(f"HITL queue query failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load HITL queue")


@app.get("/api/tf-records", response_model=PaginatedResponse)
async def get_tf_records(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user)
):
    """
    Tuition & fees records for user's institution.
    Optional status filter.
    """
    sb = get_supabase()
    inst_id = user["institution_id"]

    try:
        query = sb.table("tuition_fees_records").select("*").eq("institution_id", inst_id)

        if status:
            query = query.eq("status", status)

        # Get total
        result = query.execute()
        total = len(result.data)

        # Paginate
        offset = (page - 1) * limit
        tf_response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

        items = []
        for record in tf_response.data:
            # Get student and term names
            student_response = sb.table("students").select("first_name, last_name").eq("id", record["student_id"]).single().execute()
            student = student_response.data or {"first_name": "Unknown", "last_name": ""}

            term_response = sb.table("terms").select("term_name").eq("id", record["term_id"]).single().execute()
            term = term_response.data or {"term_name": "Unknown"}

            items.append(TFRecord(
                id=record["id"],
                student_name=f"{student['first_name']} {student['last_name']}",
                student_id=record["student_id"],
                term_name=term["term_name"],
                chapter=record.get("chapter"),
                gross_tuition=record.get("gross_tuition"),
                aid_amount=record.get("aid_amount"),
                net_tuition=record.get("net_tuition"),
                fees=record.get("fees"),
                status=record["status"],
                created_at=record["created_at"]
            ))

        has_next = (offset + limit) < total
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_next=has_next
        )
    except Exception as e:
        logger.error(f"T&F records query failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load T&F records")


@app.post("/api/process-student/{student_id}", response_model=ProcessStudentResponse)
async def process_student(
    student_id: int,
    user=Depends(get_current_user)
):
    """
    Run decision tree + pipeline on a student.
    Stores results in enrollments and course_schedules tables.
    Returns full result.
    """
    sb = get_supabase()
    inst_id = user["institution_id"]

    try:
        # Get student
        student_response = sb.table("students").select("*").eq("id", student_id).eq("institution_id", inst_id).single().execute()

        if not student_response.data:
            raise HTTPException(status_code=404, detail="Student not found")

        student = student_response.data

        # For now, return stub response (full implementation would call decision_tree and pipeline)
        return ProcessStudentResponse(
            student_id=student_id,
            status="pending_decision_tree",
            decision_tree_output=None,
            pipeline_status="not_started",
            errors=None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Process student failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process student")


# ============================================================================
# ADMIN ROUTES (Superadmin only)
# ============================================================================

@app.post("/api/admin/institutions")
async def create_institution(
    request: AdminCreateInstitution,
    user=Depends(require_superadmin)
):
    """Create new institution (superadmin only)"""
    sb = get_supabase()

    try:
        sb.table("institutions").insert({
            "facility_code": request.facility_code,
            "name": request.name,
            "address": request.address,
            "active": True
        }).execute()

        return {"status": "created", "facility_code": request.facility_code}
    except Exception as e:
        logger.error(f"Create institution failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create institution")


@app.post("/api/admin/institutions/{facility_code}/weams")
async def upload_weams_programs(
    facility_code: str,
    request: AdminUploadWEAMS,
    user=Depends(require_superadmin)
):
    """
    Upload WEAMS program list for institution (superadmin only).
    """
    sb = get_supabase()

    try:
        # Verify institution exists
        inst_response = sb.table("institutions").select("facility_code").eq("facility_code", facility_code).single().execute()

        if not inst_response.data:
            raise HTTPException(status_code=404, detail="Institution not found")

        # Insert programs
        programs_to_insert = [
            {
                "institution_id": facility_code,
                "program_name": program,
                "approved": True
            }
            for program in request.programs
        ]

        sb.table("weams_programs").insert(programs_to_insert).execute()

        return {"status": "uploaded", "program_count": len(request.programs)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload WEAMS failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload WEAMS programs")


@app.post("/api/admin/sco-users")
async def create_sco_user(
    request: AdminCreateUser,
    user=Depends(require_superadmin)
):
    """
    Create new SCO user (superadmin only).
    Creates both Supabase auth user and sco_users record.
    NOTE: Simplified stub - actual implementation requires Supabase auth API.
    """
    sb = get_supabase()

    try:
        # Verify institution exists
        inst_response = sb.table("institutions").select("facility_code").eq("facility_code", request.institution_id).single().execute()

        if not inst_response.data:
            raise HTTPException(status_code=404, detail="Institution not found")

        # In production, create auth user via Supabase auth API
        # For now, return stub response
        return {
            "status": "created",
            "email": request.email,
            "institution_id": request.institution_id,
            "role": request.role,
            "note": "Supabase auth user creation requires additional auth API integration"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create SCO user failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create SCO user")


@app.get("/api/admin/metrics", response_model=List[AdminMetricsResponse])
async def get_admin_metrics(user=Depends(require_superadmin)):
    """
    Cross-institution summary metrics (superadmin only).
    """
    sb = get_supabase()

    try:
        # Get all institutions
        institutions_response = sb.table("institutions").select("facility_code, name").eq("active", True).execute()

        metrics = []
        for inst in institutions_response.data:
            facility_code = inst["facility_code"]

            # Total students
            students = sb.table("students").select("id", count="exact").eq("institution_id", facility_code).execute()
            total_students = students.count

            # Certifications submitted
            certs = sb.table("certifications_submitted").select("id", count="exact").eq("institution_id", facility_code).execute()
            certs_count = certs.count

            # Calculate rates (stub values for now)
            cert_rate = (certs_count / total_students * 100) if total_students > 0 else 0

            metrics.append(AdminMetricsResponse(
                institution_id=facility_code,
                total_students=total_students,
                certifications_submitted=certs_count,
                certification_rate=cert_rate,
                hitl_rate=5.0,  # Stub
                avg_processing_days=2.5  # Stub
            ))

        return metrics
    except Exception as e:
        logger.error(f"Get metrics failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load metrics")


@app.post("/api/admin/generate-cohort")
async def generate_cohort(
    request: AdminGenerateCohortRequest,
    user=Depends(require_superadmin)
):
    """
    Trigger synthetic data generation (superadmin only).
    NOTE: Requires generate_synthetic_cohort from scripts/
    """
    try:
        # Stub implementation
        return {
            "status": "queued",
            "facility_code": request.facility_code,
            "term": request.term,
            "count": request.count,
            "note": "Cohort generation queued for processing"
        }
    except Exception as e:
        logger.error(f"Generate cohort failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate cohort")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
