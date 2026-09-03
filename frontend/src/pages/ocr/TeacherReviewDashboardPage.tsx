import { useState } from "react";
import { Eye } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getTeacherReviewDashboard, getTeacherReviewQueue } from "@/api/teacherReviewDashboard";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { AnswerEvaluation } from "@/types/officialExam";
import type { TeacherReviewFilters } from "@/types/teacherReview";

interface FilterState {
  exam_id: string;
  subject_id: string;
  course_id: string;
  department_id: string;
  student_user_id: string;
  teacher_id: string;
  confidence_tier: string;
  review_status: string;
}

const EMPTY_FILTERS: FilterState = {
  exam_id: "",
  subject_id: "",
  course_id: "",
  department_id: "",
  student_user_id: "",
  teacher_id: "",
  confidence_tier: "",
  review_status: "",
};

const REVIEW_STATUS_OPTIONS = [
  "pending_review",
  "pending_confirmation",
  "auto_suggested",
  "teacher_confirmed",
  "teacher_overridden",
  "teacher_rejected",
];

/**
 * Feature 1 (ADR-041) landing screen: 5 independent summary tiles, a filter
 * bar (raw UUID inputs — no autocomplete, backend accepts them as plain
 * query params) driving both the summary and the queue table, and a
 * paginated queue of `AnswerEvaluation` rows awaiting review. Uses two raw
 * `useQuery`s (rather than `usePaginatedList`) because `getTeacherReviewQueue`
 * needs both `filters` and pagination `params`, and the query key must
 * include `filters` directly so changing a filter always refetches.
 */
export function TeacherReviewDashboardPage() {
  const navigate = useNavigate();
  const institutionId = useAppSelector((state) => state.institution.currentInstitutionId);

  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const effectiveFilters: TeacherReviewFilters = {
    exam_id: filters.exam_id.trim() || undefined,
    subject_id: filters.subject_id.trim() || undefined,
    course_id: filters.course_id.trim() || undefined,
    department_id: filters.department_id.trim() || undefined,
    student_user_id: filters.student_user_id.trim() || undefined,
    teacher_id: filters.teacher_id.trim() || undefined,
    confidence_tier: filters.confidence_tier || undefined,
    review_status: filters.review_status || undefined,
  };

  function updateFilter<K extends keyof FilterState>(key: K, value: string) {
    setFilters((previous) => ({ ...previous, [key]: value }));
    setPage(1);
  }

  const summaryQuery = useQuery({
    queryKey: ["teacher-review-dashboard", institutionId, effectiveFilters],
    queryFn: () => getTeacherReviewDashboard(effectiveFilters),
    enabled: Boolean(institutionId),
  });

  const queueQuery = useQuery({
    queryKey: ["teacher-review-queue", institutionId, effectiveFilters, page, pageSize],
    queryFn: () => getTeacherReviewQueue(effectiveFilters, { page, page_size: pageSize }),
    enabled: Boolean(institutionId),
    placeholderData: (previous) => previous,
  });

  const summary = summaryQuery.data;
  const items = queueQuery.data?.items ?? [];
  const total = queueQuery.data?.total ?? 0;
  const totalPages = queueQuery.data?.total_pages ?? 0;

  const tiles: Array<{ label: string; value: number | undefined }> = [
    { label: "Pending Review", value: summary?.pending_review_count },
    { label: "Medium Confidence", value: summary?.medium_confidence_count },
    { label: "Low Confidence", value: summary?.low_confidence_count },
    { label: "Completed Reviews", value: summary?.completed_reviews_count },
    { label: "Auto Accepted", value: summary?.auto_accepted_count },
  ];

  const columns: Column<AnswerEvaluation>[] = [
    { key: "exam_session_id", header: "Exam Session", render: (row) => row.exam_session_id },
    {
      key: "confidence_tier",
      header: "Confidence Tier",
      render: (row) =>
        row.confidence_tier ? (
          <Badge variant={statusVariant(row.confidence_tier)}>{row.confidence_tier}</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "marks",
      header: "Suggested / Max Marks",
      render: (row) => `${row.suggested_marks ?? "—"} / ${row.max_marks}`,
    },
    {
      key: "review_status",
      header: "Review Status",
      render: (row) => (
        <Badge variant={statusVariant(row.review_status)}>{formatStatusLabel(row.review_status)}</Badge>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Teacher Review Dashboard"
        description="Review AI-suggested marks across your exams, filtered by exam, subject, course, department, student, or teacher."
      />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {tiles.map((tile) => (
          <Card key={tile.label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{tile.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold tabular-nums">{tile.value ?? "—"}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <div className="w-56">
              <FormField htmlFor="filter-exam-id" label="Exam ID">
                <Input
                  id="filter-exam-id"
                  value={filters.exam_id}
                  onChange={(event) => updateFilter("exam_id", event.target.value)}
                  placeholder="Exam UUID"
                />
              </FormField>
            </div>
            <div className="w-56">
              <FormField htmlFor="filter-subject-id" label="Subject ID">
                <Input
                  id="filter-subject-id"
                  value={filters.subject_id}
                  onChange={(event) => updateFilter("subject_id", event.target.value)}
                  placeholder="Subject UUID"
                />
              </FormField>
            </div>
            <div className="w-56">
              <FormField htmlFor="filter-course-id" label="Course ID">
                <Input
                  id="filter-course-id"
                  value={filters.course_id}
                  onChange={(event) => updateFilter("course_id", event.target.value)}
                  placeholder="Course UUID"
                />
              </FormField>
            </div>
            <div className="w-56">
              <FormField htmlFor="filter-department-id" label="Department ID">
                <Input
                  id="filter-department-id"
                  value={filters.department_id}
                  onChange={(event) => updateFilter("department_id", event.target.value)}
                  placeholder="Department UUID"
                />
              </FormField>
            </div>
            <div className="w-56">
              <FormField htmlFor="filter-student-user-id" label="Student User ID">
                <Input
                  id="filter-student-user-id"
                  value={filters.student_user_id}
                  onChange={(event) => updateFilter("student_user_id", event.target.value)}
                  placeholder="Student user UUID"
                />
              </FormField>
            </div>
            <div className="w-56">
              <FormField htmlFor="filter-teacher-id" label="Teacher ID">
                <Input
                  id="filter-teacher-id"
                  value={filters.teacher_id}
                  onChange={(event) => updateFilter("teacher_id", event.target.value)}
                  placeholder="Teacher UUID"
                />
              </FormField>
            </div>
            <div className="w-48">
              <FormField htmlFor="filter-confidence-tier" label="Confidence Tier">
                <Select
                  id="filter-confidence-tier"
                  value={filters.confidence_tier}
                  onChange={(event) => updateFilter("confidence_tier", event.target.value)}
                >
                  <option value="">All Tiers</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </Select>
              </FormField>
            </div>
            <div className="w-56">
              <FormField htmlFor="filter-review-status" label="Review Status">
                <Select
                  id="filter-review-status"
                  value={filters.review_status}
                  onChange={(event) => updateFilter("review_status", event.target.value)}
                >
                  <option value="">All Statuses</option>
                  {REVIEW_STATUS_OPTIONS.map((status) => (
                    <option key={status} value={status}>
                      {status.replace(/_/g, " ")}
                    </option>
                  ))}
                </Select>
              </FormField>
            </div>
          </div>
        </CardContent>
      </Card>

      <DataTable
        columns={columns}
        rows={items}
        getRowId={(row) => row.id}
        isLoading={queueQuery.isLoading}
        isError={queueQuery.isError}
        emptyMessage="No answer evaluations found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`View evaluation ${row.id}`}
              onClick={() => navigate(`/dashboard/answer-evaluations/${row.id}`)}
            >
              <Eye className="h-4 w-4" />
            </Button>
          </div>
        )}
      />

      <PaginationControls
        page={page}
        pageSize={pageSize}
        total={total}
        totalPages={totalPages}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
      />
    </div>
  );
}
