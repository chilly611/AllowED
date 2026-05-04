"""Pydantic request/response models for all endpoints"""
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime


# ============================================================================
# Dashboard & Student Models
# ============================================================================

class DashboardResponse(BaseModel):
    """Overview counts for SCO dashboard"""
    total_students: int
    ready_for_batch: int
    hitl_pending: int
    amendments_pending: int
    submitted_today: int
    tf_pending: int


class StudentListItem(BaseModel):
    """Minimal student info for list view"""
    id: int
    name: str
    student_id_internal: str
    program: Optional[str]
    benefit_chapter: Optional[str]
    enrollment_status: str
    total_certifiable_units: Optional[float]
    training_time: Optional[str]


class StudentDetail(BaseModel):
    """Full student detail including all related data"""
    id: int
    student_id_internal: str
    first_name: str
    last_name: str
    email: Optional[str]
    dob: Optional[str]
    program: Optional[str]
    benefit_chapter: Optional[str]
    academic_level: Optional[str]
    enrollment: Optional[Dict[str, Any]]
    courses: Optional[List[Dict[str, Any]]]
    amendments: Optional[List[Dict[str, Any]]]
    tuition_fees: Optional[List[Dict[str, Any]]]
    hitl_items: Optional[List[Dict[str, Any]]]
    decision_tree_output: Optional[Dict[str, Any]]


# ============================================================================
# Approval & Certification Models
# ============================================================================

class ApproveRequest(BaseModel):
    """HITL item approval"""
    notes: str


class ApproveAmendmentRequest(BaseModel):
    """Amendment approval"""
    notes: str


class BatchCertifyRequest(BaseModel):
    """Batch certification request"""
    student_ids: Optional[List[int]] = None  # None = all ready_for_batch


class BatchCertifyResponse(BaseModel):
    """Batch certification response"""
    certified_count: int
    failed_count: int
    errors: Optional[List[Dict[str, Any]]]


# ============================================================================
# Amendment Models
# ============================================================================

class AmendmentListItem(BaseModel):
    """Amendment list view"""
    id: int
    student_name: str
    student_id: int
    amendment_reason: str
    status: str
    original_data: Optional[Dict[str, Any]]
    revised_data: Optional[Dict[str, Any]]
    created_at: str


# ============================================================================
# Audit Log Models
# ============================================================================

class AuditLogEntry(BaseModel):
    """Immutable audit log entry"""
    id: int
    action: str
    entity_type: str
    entity_id: Optional[int]
    user_email: Optional[str]
    details: Optional[Dict[str, Any]]
    created_at: str


# ============================================================================
# HITL & Queue Models
# ============================================================================

class HITLItem(BaseModel):
    """Human-In-The-Loop queue item"""
    id: int
    student_name: str
    student_id: int
    flag_type: str
    flag_reason: str
    priority: str
    status: str
    created_at: str


class TFRecord(BaseModel):
    """Tuition & Fees record"""
    id: int
    student_name: str
    student_id: int
    term_name: str
    chapter: Optional[str]
    gross_tuition: Optional[float]
    aid_amount: Optional[float]
    net_tuition: Optional[float]
    fees: Optional[float]
    status: str
    created_at: str


# ============================================================================
# Admin Models
# ============================================================================

class AdminCreateInstitution(BaseModel):
    """Create new institution"""
    facility_code: str
    name: str
    address: Optional[str]


class AdminCreateUser(BaseModel):
    """Create SCO user (superadmin only)"""
    email: str
    password: str
    full_name: str
    institution_id: str
    role: str = "sco"


class AdminUploadWEAMS(BaseModel):
    """WEAMS program list"""
    programs: List[str]


class AdminMetricsResponse(BaseModel):
    """Cross-institution metrics"""
    institution_id: str
    total_students: int
    certifications_submitted: int
    certification_rate: float
    hitl_rate: float
    avg_processing_days: float


class AdminGenerateCohortRequest(BaseModel):
    """Synthetic cohort generation"""
    facility_code: str
    term: str
    count: int


# ============================================================================
# Process Student Models
# ============================================================================

class ProcessStudentRequest(BaseModel):
    """Trigger decision tree + pipeline for student"""
    student_id: int


class ProcessStudentResponse(BaseModel):
    """Result of processing a student"""
    student_id: int
    status: str
    decision_tree_output: Optional[Dict[str, Any]]
    pipeline_status: str
    errors: Optional[List[str]]


# ============================================================================
# Pagination
# ============================================================================

class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper"""
    items: List[Any]
    total: int
    page: int
    limit: int
    has_next: bool
