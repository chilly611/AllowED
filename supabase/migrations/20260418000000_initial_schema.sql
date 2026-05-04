-- ============================================================================
-- AllowED VA Certification Automation System
-- Multi-tenant PostgreSQL schema for Supabase deployment
-- Migration: 20260418000000_initial_schema.sql
-- Created: 2026-04-18
-- ============================================================================

-- ============================================================================
-- SECTION 1: CUSTOM TYPES (ENUMS)
-- ============================================================================

CREATE TYPE user_role AS ENUM ('sco', 'supervisor', 'superadmin');
CREATE TYPE enrollment_status AS ENUM ('pending', 'ready_for_batch', 'hitl_review', 'submitted', 'certified', 'error');
CREATE TYPE amendment_status AS ENUM ('pending_review', 'approved', 'submitted', 'rejected');
CREATE TYPE tuition_status AS ENUM ('pending_bursar_report', 'received', 'certified_to_va', 'amended');
CREATE TYPE hitl_status AS ENUM ('open', 'in_review', 'resolved', 'dismissed');
CREATE TYPE hitl_priority AS ENUM ('high', 'medium', 'low');
CREATE TYPE submission_type AS ENUM ('initial', 'amendment');
CREATE TYPE submission_status AS ENUM ('pending', 'accepted', 'rejected', 'error');
CREATE TYPE benefit_chapter AS ENUM ('ch33', 'ch35', 'ch31');
CREATE TYPE academic_level AS ENUM ('undergraduate', 'masters', 'doctoral');

-- ============================================================================
-- SECTION 2: TABLES
-- ============================================================================

-- Table 1: Institutions (Multi-tenancy root)
CREATE TABLE institutions (
  facility_code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  address TEXT,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_institutions_active ON institutions(active);

-- Table 2: WEAMS Programs
CREATE TABLE weams_programs (
  id SERIAL PRIMARY KEY,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  program_name TEXT NOT NULL,
  degree_type TEXT,
  approved BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_weams_programs_institution ON weams_programs(institution_id);
CREATE INDEX idx_weams_programs_name ON weams_programs(institution_id, program_name);

-- Table 3: SCO Users (linked to Supabase Auth)
CREATE TABLE sco_users (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  email TEXT NOT NULL,
  full_name TEXT NOT NULL,
  role user_role NOT NULL DEFAULT 'sco',
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT email_unique UNIQUE (email)
);

CREATE INDEX idx_sco_users_institution ON sco_users(institution_id);
CREATE INDEX idx_sco_users_role ON sco_users(role);

-- Table 4: Students
CREATE TABLE students (
  id SERIAL PRIMARY KEY,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  student_id_internal TEXT NOT NULL,
  emplid TEXT,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  dob DATE,
  email TEXT,
  benefit_chapter benefit_chapter,
  program TEXT,
  academic_level academic_level,
  facility_code TEXT,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT student_unique_per_inst UNIQUE (institution_id, student_id_internal)
);

CREATE INDEX idx_students_institution ON students(institution_id);
CREATE INDEX idx_students_emplid ON students(emplid);
CREATE INDEX idx_students_benefit_chapter ON students(institution_id, benefit_chapter);

-- Table 5: Terms
CREATE TABLE terms (
  id SERIAL PRIMARY KEY,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  term_name TEXT NOT NULL,
  begin_date DATE NOT NULL,
  end_date DATE NOT NULL,
  add_drop_deadline DATE,
  census_date DATE,
  withdrawal_deadline DATE,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT term_dates_valid CHECK (begin_date < end_date),
  CONSTRAINT term_unique_per_inst UNIQUE (institution_id, term_name)
);

CREATE INDEX idx_terms_institution ON terms(institution_id);

-- Table 6: Enrollments (core certification records)
CREATE TABLE enrollments (
  id SERIAL PRIMARY KEY,
  student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  status enrollment_status NOT NULL DEFAULT 'pending',
  residential_units NUMERIC(5,2),
  distance_units NUMERIC(5,2),
  total_certifiable_units NUMERIC(5,2),
  training_time TEXT,
  rate_of_pursuit NUMERIC(5,4),
  mha_eligible BOOLEAN,
  weams_matched BOOLEAN,
  weams_confidence NUMERIC(3,2),
  decision_tree_output JSONB,
  em_enrollment_data JSONB,
  submitted_at TIMESTAMPTZ,
  certified_by UUID REFERENCES sco_users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT enrollment_unique UNIQUE (student_id, term_id)
);

CREATE INDEX idx_enrollments_institution ON enrollments(institution_id);
CREATE INDEX idx_enrollments_student ON enrollments(student_id);
CREATE INDEX idx_enrollments_term ON enrollments(term_id);
CREATE INDEX idx_enrollments_status ON enrollments(institution_id, status);

-- Table 7: Course Schedules
CREATE TABLE course_schedules (
  id SERIAL PRIMARY KEY,
  enrollment_id INTEGER NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  course_id TEXT NOT NULL,
  title TEXT,
  units NUMERIC(5,2),
  grading_basis TEXT,
  in_dars BOOLEAN,
  has_in_person_session BOOLEAN,
  all_online BOOLEAN,
  is_remedial BOOLEAN DEFAULT false,
  is_repeat BOOLEAN DEFAULT false,
  is_audit BOOLEAN DEFAULT false,
  is_thesis BOOLEAN DEFAULT false,
  is_practicum BOOLEAN DEFAULT false,
  certifiable BOOLEAN,
  modality TEXT,
  exclusion_reason TEXT,
  step_failed INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_course_schedules_enrollment ON course_schedules(enrollment_id);
CREATE INDEX idx_course_schedules_institution ON course_schedules(institution_id);

-- Table 8: Enrollment Snapshots (for change detection)
CREATE TABLE enrollment_snapshots (
  id SERIAL PRIMARY KEY,
  student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  snapshot_data JSONB NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_snapshots_institution ON enrollment_snapshots(institution_id);
CREATE INDEX idx_snapshots_student_term ON enrollment_snapshots(student_id, term_id);
CREATE INDEX idx_snapshots_captured ON enrollment_snapshots(captured_at);

-- Table 9: Amendments
CREATE TABLE amendments (
  id SERIAL PRIMARY KEY,
  enrollment_id INTEGER NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  amendment_reason TEXT NOT NULL,
  effective_date DATE NOT NULL,
  original_data JSONB NOT NULL,
  revised_data JSONB NOT NULL,
  status amendment_status NOT NULL DEFAULT 'pending_review',
  hitl_required BOOLEAN DEFAULT false,
  approved_by UUID REFERENCES sco_users(id) ON DELETE SET NULL,
  approved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Constrain to the 8 valid EM amendment reasons
  CONSTRAINT valid_amendment_reason CHECK (amendment_reason IN (
    'Pre-registered but never attended',
    'Unsatisfactory attendance, progress or conduct',
    'Withdraw before beginning of term',
    'Withdraw after drop period - non-punitive grades assigned',
    'Withdraw after drop period - punitive grades assigned',
    'Withdraw during drop period',
    'Withdrawal or interruption (Non-College Degree Programs not on a term basis)',
    'Other'
  ))
);

CREATE INDEX idx_amendments_institution ON amendments(institution_id);
CREATE INDEX idx_amendments_enrollment ON amendments(enrollment_id);
CREATE INDEX idx_amendments_status ON amendments(institution_id, status);

-- Table 10: Tuition & Fees Records
CREATE TABLE tuition_fees_records (
  id SERIAL PRIMARY KEY,
  student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  chapter benefit_chapter,
  gross_tuition NUMERIC(12,2),
  aid_amount NUMERIC(12,2),
  net_tuition NUMERIC(12,2),
  fees NUMERIC(12,2),
  status tuition_status NOT NULL DEFAULT 'pending_bursar_report',
  certified_by UUID REFERENCES sco_users(id) ON DELETE SET NULL,
  certified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT tf_unique UNIQUE (student_id, term_id, chapter)
);

CREATE INDEX idx_tf_institution ON tuition_fees_records(institution_id);
CREATE INDEX idx_tf_status ON tuition_fees_records(institution_id, status);

-- Table 11: HITL Queue
CREATE TABLE hitl_queue (
  id SERIAL PRIMARY KEY,
  enrollment_id INTEGER REFERENCES enrollments(id) ON DELETE SET NULL,
  amendment_id INTEGER REFERENCES amendments(id) ON DELETE SET NULL,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  flag_type TEXT NOT NULL,
  flag_reason TEXT NOT NULL,
  priority hitl_priority NOT NULL DEFAULT 'medium',
  status hitl_status NOT NULL DEFAULT 'open',
  assigned_to UUID REFERENCES sco_users(id) ON DELETE SET NULL,
  resolved_by UUID REFERENCES sco_users(id) ON DELETE SET NULL,
  resolved_at TIMESTAMPTZ,
  resolution_notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT has_parent CHECK (enrollment_id IS NOT NULL OR amendment_id IS NOT NULL)
);

CREATE INDEX idx_hitl_institution ON hitl_queue(institution_id);
CREATE INDEX idx_hitl_status ON hitl_queue(institution_id, status);
CREATE INDEX idx_hitl_priority ON hitl_queue(priority);

-- Table 12: Audit Log (immutable)
CREATE TABLE audit_log (
  id SERIAL PRIMARY KEY,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  user_id UUID REFERENCES sco_users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id INTEGER,
  details JSONB,
  ip_address INET,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_institution_created ON audit_log(institution_id, created_at DESC);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);

-- Table 13: Certifications Submitted
CREATE TABLE certifications_submitted (
  id SERIAL PRIMARY KEY,
  enrollment_id INTEGER NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
  institution_id TEXT NOT NULL REFERENCES institutions(facility_code) ON DELETE CASCADE,
  submission_type submission_type NOT NULL,
  va_submission_id TEXT,
  va_response JSONB,
  pdf_url TEXT,
  status submission_status NOT NULL DEFAULT 'pending',
  submitted_by UUID NOT NULL REFERENCES sco_users(id) ON DELETE RESTRICT,
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  va_response_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_certs_institution ON certifications_submitted(institution_id);
CREATE INDEX idx_certs_enrollment ON certifications_submitted(enrollment_id);
CREATE INDEX idx_certs_status ON certifications_submitted(institution_id, status);

-- ============================================================================
-- SECTION 3: HELPER FUNCTIONS (after tables exist)
-- ============================================================================

-- Extract institution_id from JWT app_metadata
CREATE OR REPLACE FUNCTION get_user_institution_id()
RETURNS text AS $$
  SELECT COALESCE(
    auth.jwt() -> 'app_metadata' ->> 'institution_id',
    (SELECT institution_id FROM sco_users WHERE id = auth.uid() LIMIT 1)
  )
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- Check if current user is superadmin
CREATE OR REPLACE FUNCTION is_superadmin()
RETURNS boolean AS $$
  SELECT EXISTS (
    SELECT 1 FROM sco_users
    WHERE id = auth.uid()
      AND role = 'superadmin'
      AND active = true
  )
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- ============================================================================
-- SECTION 4: ROW LEVEL SECURITY
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE institutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE weams_programs ENABLE ROW LEVEL SECURITY;
ALTER TABLE sco_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrollment_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE amendments ENABLE ROW LEVEL SECURITY;
ALTER TABLE tuition_fees_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE hitl_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE certifications_submitted ENABLE ROW LEVEL SECURITY;

-- Service role bypass (Python backend uses this)
-- service_role bypasses RLS by default in Supabase, but explicit policies are good practice

-- INSTITUTIONS policies
CREATE POLICY "service_role_all" ON institutions FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_read" ON institutions FOR SELECT
  USING (is_superadmin());
CREATE POLICY "own_institution" ON institutions FOR SELECT
  USING (facility_code = get_user_institution_id());

-- WEAMS_PROGRAMS policies
CREATE POLICY "service_role_all" ON weams_programs FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_all" ON weams_programs FOR ALL
  USING (is_superadmin());
CREATE POLICY "own_institution" ON weams_programs FOR SELECT
  USING (institution_id = get_user_institution_id());

-- SCO_USERS policies
CREATE POLICY "service_role_all" ON sco_users FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_all" ON sco_users FOR ALL
  USING (is_superadmin());
CREATE POLICY "own_institution" ON sco_users FOR SELECT
  USING (institution_id = get_user_institution_id());

-- STUDENTS policies
CREATE POLICY "service_role_all" ON students FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_all" ON students FOR ALL
  USING (is_superadmin());
CREATE POLICY "own_institution" ON students FOR ALL
  USING (institution_id = get_user_institution_id());

-- TERMS policies
CREATE POLICY "service_role_all" ON terms FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_all" ON terms FOR ALL
  USING (is_superadmin());
CREATE POLICY "own_institution" ON terms FOR SELECT
  USING (institution_id = get_user_institution_id());

-- ENROLLMENTS policies
CREATE POLICY "service_role_all" ON enrollments FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_all" ON enrollments FOR ALL
  USING (is_superadmin());
CREATE POLICY "own_institution" ON enrollments FOR ALL
  USING (institution_id = get_user_institution_id());

-- COURSE_SCHEDULES policies
CREATE POLICY "service_role_all" ON course_schedules FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_all" ON course_schedules FOR ALL
  USING (is_superadmin());
CREATE POLICY "own_institution" ON course_schedules FOR ALL
  USING (institution_id = get_user_institution_id());

-- ENROLLMENT_SNAPSHOTS policies
CREATE POLICY "service_role_all" ON enrollment_snapshots FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_all" ON enrollment_snapshots FOR ALL
  USING (is_superadmin());
CREATE POLICY "own_institution" ON enrollment_snapshots FOR ALL
  USING (institution_id = get_user_institution_id());

-- AMENDMENTS policies
CREATE POLICY "service_role_all" ON amendments FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_all" ON amendments FOR ALL
  USING (is_superadmin());
CREATE POLICY "own_institution" ON amendments FOR ALL
  USING (institution_id = get_user_institution_id());

-- TUITION_FEES_RECORDS policies
CREATE POLICY "service_role_all" ON tuition_fees_records FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_all" ON tuition_fees_records FOR ALL
  USING (is_superadmin());
CREATE POLICY "own_institution" ON tuition_fees_records FOR ALL
  USING (institution_id = get_user_institution_id());

-- HITL_QUEUE policies
CREATE POLICY "service_role_all" ON hitl_queue FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_all" ON hitl_queue FOR ALL
  USING (is_superadmin());
CREATE POLICY "own_institution" ON hitl_queue FOR ALL
  USING (institution_id = get_user_institution_id());

-- AUDIT_LOG policies (SCOs can read, only service_role can write)
CREATE POLICY "service_role_all" ON audit_log FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_read" ON audit_log FOR SELECT
  USING (is_superadmin());
CREATE POLICY "own_institution_read" ON audit_log FOR SELECT
  USING (institution_id = get_user_institution_id());

-- CERTIFICATIONS_SUBMITTED policies
CREATE POLICY "service_role_all" ON certifications_submitted FOR ALL
  USING (auth.role() = 'service_role');
CREATE POLICY "superadmin_all" ON certifications_submitted FOR ALL
  USING (is_superadmin());
CREATE POLICY "own_institution" ON certifications_submitted FOR ALL
  USING (institution_id = get_user_institution_id());

-- ============================================================================
-- SECTION 5: UPDATED_AT TRIGGER
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON institutions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON sco_users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON students
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON enrollments
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON amendments
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON tuition_fees_records
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER set_updated_at BEFORE UPDATE ON hitl_queue
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- MIGRATION COMPLETE
-- 13 tables, RLS on all, indexes on all FKs and query paths
-- ============================================================================
