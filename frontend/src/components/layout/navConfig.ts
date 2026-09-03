import {
  BarChart3,
  Bell,
  BookCheck,
  BrainCircuit,
  Building2,
  CalendarClock,
  CalendarRange,
  CheckSquare,
  ClipboardCheck,
  ClipboardList,
  Cpu,
  FileBarChart,
  FileBarChart2,
  FileQuestion,
  FileScan,
  FileSearch2,
  FileStack,
  Gauge,
  GraduationCap,
  KeySquare,
  Layers,
  LandPlot,
  LayoutDashboard,
  Library,
  ListChecks,
  ListTree,
  Network,
  Package,
  School,
  ScanText,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  UploadCloud,
  User,
  UserSquare2,
  Users,
  type LucideIcon,
} from "lucide-react";

export interface NavLeaf {
  label: string;
  to: string;
  icon: LucideIcon;
  end?: boolean;
  /** Requires all of these permission codes; omitted = always visible.
   * These are the exact same codes the flat pre-redesign sidebar used —
   * this redesign only regroups existing links, it grants nothing new. */
  requiredPermissions?: string[];
}

export interface NavGroup {
  id: string;
  label: string;
  icon: LucideIcon;
  items: NavLeaf[];
  /** Collapsed by default when the sidebar first mounts (still expands on
   * click, or automatically if the active route lives inside it). */
  defaultCollapsed?: boolean;
}

/** Always visible, ungated, first in the tree. */
export const DASHBOARD_ITEM: NavLeaf = {
  label: "Dashboard",
  to: "/dashboard",
  icon: LayoutDashboard,
  end: true,
};

/**
 * Workflow-oriented navigation groups (Module 12 IA redesign). Every `to`
 * below is a real, already-existing route from `routes/index.tsx`; every
 * `requiredPermissions` is a real, already-existing permission code from
 * the pre-redesign flat `NAV_ITEMS` list this replaces. No route, page, or
 * permission was added, removed, or renamed on the backend or router —
 * only how they're grouped and labeled here changed.
 *
 * A few of the source spec's conceptual sub-items (e.g. "Active/Completed/
 * Archived Packages" under Evaluation Packages, or "OCR Queue" vs.
 * "OCR Status") don't correspond to distinct real routes — IntelliGrade has
 * one real dashboard per concern, not a separate page per lifecycle state.
 * Rather than invent placeholder routes, those concepts are represented as
 * a single real link to the dashboard that already covers them (see
 * `DASHBOARD_REDESIGN_NOTES.md`-equivalent context in the module report).
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: "evaluation-packages",
    label: "Evaluation Packages",
    icon: Package,
    items: [
      {
        label: "Official Exam Documents",
        to: "/dashboard/official-exam-documents",
        icon: FileSearch2,
        requiredPermissions: ["official_exam_documents:read"],
      },
    ],
  },
  {
    id: "student-answer-scripts",
    label: "Student Answer Scripts",
    icon: FileScan,
    items: [
      {
        label: "Answer Scripts",
        to: "/dashboard/answer-scripts",
        icon: FileScan,
        requiredPermissions: ["answer_scripts:read"],
      },
      {
        label: "Upload Queue",
        to: "/dashboard/upload-queue",
        icon: UploadCloud,
        requiredPermissions: ["upload_jobs:read"],
      },
      {
        label: "OCR Status",
        to: "/dashboard/ocr-status",
        icon: ScanText,
        requiredPermissions: ["ocr_jobs:read"],
      },
    ],
  },
  {
    id: "ai-evaluation",
    label: "AI Evaluation",
    icon: BrainCircuit,
    items: [
      {
        label: "AI Reference Answers",
        to: "/dashboard/ai-reference-answers",
        icon: FileSearch2,
        requiredPermissions: ["ai_reference_answers:read"],
      },
      {
        label: "Answer Evaluations",
        to: "/dashboard/answer-evaluations",
        icon: Gauge,
        requiredPermissions: ["answer_evaluations:read"],
      },
    ],
  },
  {
    id: "teacher-review",
    label: "Teacher Review",
    icon: ListChecks,
    items: [
      {
        label: "Review Dashboard",
        to: "/dashboard/teacher-review",
        icon: ListChecks,
        requiredPermissions: ["teacher_review_dashboard:read"],
      },
    ],
  },
  {
    id: "results",
    label: "Results",
    icon: FileBarChart,
    items: [
      {
        label: "Exam Results",
        to: "/dashboard/exam-results",
        icon: FileBarChart,
        requiredPermissions: ["exam_results:read"],
      },
    ],
  },
  {
    id: "reports-analytics",
    label: "Reports & Analytics",
    icon: BarChart3,
    items: [
      {
        label: "Analytics",
        to: "/dashboard/analytics",
        icon: BarChart3,
        requiredPermissions: ["analytics:read"],
      },
      {
        label: "Reports",
        to: "/dashboard/reports",
        icon: FileBarChart2,
        requiredPermissions: ["reports:read"],
      },
    ],
  },
  {
    id: "administration",
    label: "Administration",
    icon: Settings2,
    items: [
      {
        label: "AI Providers",
        to: "/dashboard/ai-providers",
        icon: BrainCircuit,
        requiredPermissions: ["ai_providers:read"],
      },
      {
        label: "AI Configuration",
        to: "/dashboard/ai-configurations",
        icon: SlidersHorizontal,
        requiredPermissions: ["ai_configurations:read"],
      },
      {
        label: "OCR Providers",
        to: "/dashboard/ocr-providers",
        icon: Cpu,
        requiredPermissions: ["ocr_providers:read"],
      },
      {
        label: "OCR Configuration",
        to: "/dashboard/ocr-configurations",
        icon: Settings2,
        requiredPermissions: ["ocr_configurations:read"],
      },
    ],
  },
  {
    id: "academic-setup",
    label: "Academic & Assessment Setup",
    icon: GraduationCap,
    defaultCollapsed: true,
    items: [
      {
        label: "Institutions",
        to: "/dashboard/institutions",
        icon: Building2,
        requiredPermissions: ["institutions:read"],
      },
      {
        label: "Campuses",
        to: "/dashboard/campuses",
        icon: LandPlot,
        requiredPermissions: ["campuses:read"],
      },
      {
        label: "Departments",
        to: "/dashboard/departments",
        icon: Network,
        requiredPermissions: ["departments:read"],
      },
      {
        label: "Programs",
        to: "/dashboard/programs",
        icon: GraduationCap,
        requiredPermissions: ["programs:read"],
      },
      {
        label: "Courses",
        to: "/dashboard/courses",
        icon: Library,
        requiredPermissions: ["courses:read"],
      },
      {
        label: "Academic Years",
        to: "/dashboard/academic-years",
        icon: CalendarRange,
        requiredPermissions: ["academic_years:read"],
      },
      {
        label: "Semesters",
        to: "/dashboard/semesters",
        icon: Layers,
        requiredPermissions: ["semesters:read"],
      },
      {
        label: "Sections",
        to: "/dashboard/sections",
        icon: School,
        requiredPermissions: ["sections:read"],
      },
      {
        label: "Subjects",
        to: "/dashboard/subjects",
        icon: ClipboardList,
        requiredPermissions: ["subjects:read"],
      },
      {
        label: "Teacher Assignments",
        to: "/dashboard/teacher-assignments",
        icon: UserSquare2,
        requiredPermissions: ["teacher_assignments:read"],
      },
      {
        label: "Student Enrollments",
        to: "/dashboard/student-enrollments",
        icon: Users,
        requiredPermissions: ["student_enrollments:read"],
      },
      {
        label: "Assessments",
        to: "/dashboard/assessments",
        icon: BookCheck,
        requiredPermissions: ["assessments:read"],
      },
      {
        label: "Exams",
        to: "/dashboard/exams",
        icon: ClipboardCheck,
        requiredPermissions: ["exams:read"],
      },
      {
        label: "Exam Schedules",
        to: "/dashboard/exam-schedules",
        icon: CalendarClock,
        requiredPermissions: ["exam_schedules:read"],
      },
      {
        label: "Question Bank",
        to: "/dashboard/questions",
        icon: FileQuestion,
        requiredPermissions: ["questions:read"],
      },
      {
        label: "Question Approvals",
        to: "/dashboard/question-approvals",
        icon: CheckSquare,
        requiredPermissions: ["questions:approve"],
      },
      {
        label: "Blueprints",
        to: "/dashboard/question-blueprints",
        icon: ListTree,
        requiredPermissions: ["question_blueprints:read"],
      },
      {
        label: "Question Papers",
        to: "/dashboard/question-papers",
        icon: FileStack,
        requiredPermissions: ["question_papers:read"],
      },
      {
        label: "Rubrics",
        to: "/dashboard/rubrics",
        icon: ClipboardList,
        requiredPermissions: ["rubrics:read"],
      },
      {
        label: "Answer Keys",
        to: "/dashboard/answer-keys",
        icon: KeySquare,
        requiredPermissions: ["answer_keys:read"],
      },
    ],
  },
];

/** Personal/utility links — not part of the workflow taxonomy, kept as a
 * small ungrouped cluster rather than forced into an unrelated group. */
export const UTILITY_ITEMS: NavLeaf[] = [
  { label: "Search", to: "/dashboard/search", icon: Search, requiredPermissions: ["search:read"] },
  {
    label: "Notifications",
    to: "/dashboard/notifications",
    icon: Bell,
    requiredPermissions: ["notifications:read"],
  },
  { label: "Sessions", to: "/dashboard/sessions", icon: ShieldCheck },
  { label: "Profile", to: "/dashboard/profile", icon: User },
];
