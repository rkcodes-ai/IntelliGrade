/**
 * Types mirroring the backend's Academic Domain (Module 03) Pydantic
 * schemas (`backend/app/schemas/*.py`) field-for-field, including snake_case
 * casing — same convention as `types/auth.ts` (see its file-level comment).
 */

export interface Institution {
  id: string;
  name: string;
  code: string;
  institution_type: string;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  established_year: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InstitutionCreate {
  name: string;
  code: string;
  institution_type: string;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  postal_code?: string | null;
  phone?: string | null;
  email?: string | null;
  website?: string | null;
  established_year?: number | null;
}

export type InstitutionUpdate = Partial<InstitutionCreate> & { is_active?: boolean };

export interface UserInstitution {
  id: string;
  user_id: string;
  institution_id: string;
  is_primary: boolean;
  is_active: boolean;
  joined_at: string;
}

export interface Campus {
  id: string;
  institution_id: string;
  name: string;
  code: string;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  is_main_campus: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CampusCreate {
  name: string;
  code: string;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  is_main_campus?: boolean;
}

export type CampusUpdate = Partial<CampusCreate> & { is_active?: boolean };

export interface Department {
  id: string;
  institution_id: string;
  campus_id: string;
  name: string;
  code: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DepartmentCreate {
  campus_id: string;
  name: string;
  code: string;
  description?: string | null;
}

export type DepartmentUpdate = Partial<DepartmentCreate> & { is_active?: boolean };

export type DegreeType = "ug" | "pg" | "diploma" | "doctorate" | "certificate";

export interface Program {
  id: string;
  institution_id: string;
  department_id: string;
  name: string;
  code: string;
  degree_type: string;
  duration_years: number;
  total_semesters: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProgramCreate {
  department_id: string;
  name: string;
  code: string;
  degree_type: DegreeType;
  duration_years: number;
  total_semesters: number;
}

export type ProgramUpdate = Partial<ProgramCreate> & { is_active?: boolean };

export interface Course {
  id: string;
  institution_id: string;
  program_id: string;
  name: string;
  code: string;
  description: string | null;
  duration_years: number | null;
  total_semesters: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CourseCreate {
  program_id: string;
  name: string;
  code: string;
  description?: string | null;
  duration_years?: number | null;
  total_semesters?: number | null;
}

export type CourseUpdate = Partial<CourseCreate> & { is_active?: boolean };

export type AcademicYearStatus = "planned" | "active" | "completed" | "archived";

export interface AcademicYear {
  id: string;
  institution_id: string;
  year_label: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AcademicYearCreate {
  year_label: string;
  start_date: string;
  end_date: string;
  is_current?: boolean;
  status?: AcademicYearStatus;
}

export type AcademicYearUpdate = Partial<AcademicYearCreate>;

export type SemesterTermType = "odd" | "even";
export type SemesterStatus = "planned" | "active" | "completed" | "archived";

export interface Semester {
  id: string;
  institution_id: string;
  academic_year_id: string;
  name: string;
  semester_number: number;
  term_type: string;
  start_date: string;
  end_date: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SemesterCreate {
  academic_year_id: string;
  name: string;
  semester_number: number;
  term_type: SemesterTermType;
  start_date: string;
  end_date: string;
  status?: SemesterStatus;
}

export type SemesterUpdate = Partial<SemesterCreate>;

export interface Section {
  id: string;
  institution_id: string;
  batch_id: string;
  name: string;
  max_capacity: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SectionCreate {
  batch_id: string;
  name: string;
  max_capacity: number;
}

export type SectionUpdate = Partial<SectionCreate> & { is_active?: boolean };

export interface Subject {
  id: string;
  institution_id: string;
  course_id: string;
  subject_category_id: string;
  code: string;
  name: string;
  credits: string;
  semester_number: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SubjectCreate {
  course_id: string;
  subject_category_id: string;
  code: string;
  name: string;
  credits: number;
  semester_number: number;
}

export type SubjectUpdate = Partial<SubjectCreate> & { is_active?: boolean };

export type AssignmentRole = "primary" | "assistant" | "substitute";

export interface TeacherAssignment {
  id: string;
  institution_id: string;
  teacher_user_id: string;
  subject_allocation_id: string;
  assignment_role: string;
  assigned_from: string;
  assigned_to: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TeacherAssignmentCreate {
  teacher_user_id: string;
  subject_allocation_id: string;
  assignment_role?: AssignmentRole;
  assigned_from: string;
  assigned_to?: string | null;
}

export type TeacherAssignmentUpdate = Partial<TeacherAssignmentCreate> & { is_active?: boolean };

export interface StudentEnrollment {
  id: string;
  institution_id: string;
  student_user_id: string;
  batch_id: string;
  section_id: string;
  course_id: string;
  academic_year_id: string;
  semester_id: string;
  academic_status_id: string;
  roll_number: string;
  enrollment_date: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StudentEnrollmentCreate {
  student_user_id: string;
  batch_id: string;
  section_id: string;
  course_id: string;
  academic_year_id: string;
  semester_id: string;
  academic_status_id: string;
  roll_number: string;
  enrollment_date: string;
}

export type StudentEnrollmentUpdate = Partial<StudentEnrollmentCreate> & { is_active?: boolean };

/**
 * Read-only supporting entities: no dedicated management screen in this
 * module (only the 11 screens explicitly listed for the UI ship), but their
 * rows are still required as FK selections on Section/Subject/Teacher
 * Assignment/Student Enrollment forms — the backend has full CRUD for
 * them already (out of this module's UI scope to expose directly).
 */
export interface Batch {
  id: string;
  institution_id: string;
  course_id: string;
  name: string;
  start_year: number;
  end_year: number;
  is_active: boolean;
}

export interface SubjectCategory {
  id: string;
  institution_id: string;
  code: string;
  name: string;
  is_active: boolean;
}

export interface SubjectAllocation {
  id: string;
  institution_id: string;
  subject_id: string;
  section_id: string;
  semester_id: string;
  academic_year_id: string;
  teacher_user_id: string;
  room_id: string | null;
  is_active: boolean;
}

export interface AcademicStatus {
  id: string;
  institution_id: string;
  code: string;
  name: string;
  is_terminal: boolean;
  is_active: boolean;
}
