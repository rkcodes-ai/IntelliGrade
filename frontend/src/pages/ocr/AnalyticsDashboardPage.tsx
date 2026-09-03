import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";

import { getAnalyticsOverview, getQuestionWiseAnalytics } from "@/api/analytics";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import type { AnalyticsFilters, QuestionPerformance } from "@/types/teacherReview";

interface AnalyticsFilterForm {
  exam_id: string;
  subject_id: string;
  course_id: string;
  department_id: string;
}

const emptyFilters: AnalyticsFilterForm = {
  exam_id: "",
  subject_id: "",
  course_id: "",
  department_id: "",
};

const CONFIDENCE_TIERS = ["high", "medium", "low"] as const;

function formatValue(value: string | null): string {
  return value ?? "—";
}

function formatPercent(value: string | null): string {
  return value == null ? "—" : `${value}%`;
}

function formatRatioPercent(value: string | null): string {
  return value == null ? "—" : `${value}%`;
}

/**
 * Analytics Dashboard (Module 07, Feature 7, ADR-044): an optional-filter
 * overview of result/confidence/teacher-review-override stats, plus an
 * on-demand question-wise performance breakdown for a single exam (that
 * endpoint requires an exam id, so it's a separate trigger rather than part
 * of the top filter bar).
 */
export function AnalyticsDashboardPage() {
  const [filters, setFilters] = useState<AnalyticsFilterForm>(emptyFilters);

  const appliedFilters: AnalyticsFilters = {
    exam_id: filters.exam_id.trim() || undefined,
    subject_id: filters.subject_id.trim() || undefined,
    course_id: filters.course_id.trim() || undefined,
    department_id: filters.department_id.trim() || undefined,
  };

  const {
    data: overview,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["analytics-overview", appliedFilters],
    queryFn: () => getAnalyticsOverview(appliedFilters),
  });

  const [questionExamId, setQuestionExamId] = useState("");
  const [loadedExamId, setLoadedExamId] = useState<string | null>(null);

  const {
    data: questionWise,
    isLoading: isQuestionLoading,
    isError: isQuestionError,
  } = useQuery({
    queryKey: ["question-wise-analytics", loadedExamId],
    queryFn: () => getQuestionWiseAnalytics(loadedExamId!),
    enabled: Boolean(loadedExamId),
  });

  function handleLoadQuestionWise(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!questionExamId.trim()) return;
    setLoadedExamId(questionExamId.trim());
  }

  const questionColumns: Column<QuestionPerformance>[] = [
    { key: "question_number", header: "Question Number", render: (row) => row.question_number },
    { key: "evaluated_count", header: "Evaluated Count", render: (row) => row.evaluated_count },
    { key: "max_marks", header: "Max Marks", render: (row) => row.max_marks },
    { key: "average_marks", header: "Average Marks", render: (row) => formatValue(row.average_marks) },
    {
      key: "average_ratio",
      header: "Average Ratio",
      render: (row) => formatRatioPercent(row.average_ratio),
    },
  ];

  const confidenceTotal = overview
    ? overview.confidence_distribution.high +
      overview.confidence_distribution.medium +
      overview.confidence_distribution.low
    : 0;

  function confidenceBarWidth(count: number): string {
    return confidenceTotal > 0 ? `${Math.round((count / confidenceTotal) * 100)}%` : "0%";
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Analytics Dashboard"
        description="Result, confidence, and teacher-review analytics across exams, subjects, courses, and departments."
      />

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
                  onChange={(event) => setFilters({ ...filters, exam_id: event.target.value })}
                  placeholder="Exam UUID"
                />
              </FormField>
            </div>
            <div className="w-56">
              <FormField htmlFor="filter-subject-id" label="Subject ID">
                <Input
                  id="filter-subject-id"
                  value={filters.subject_id}
                  onChange={(event) => setFilters({ ...filters, subject_id: event.target.value })}
                  placeholder="Subject UUID"
                />
              </FormField>
            </div>
            <div className="w-56">
              <FormField htmlFor="filter-course-id" label="Course ID">
                <Input
                  id="filter-course-id"
                  value={filters.course_id}
                  onChange={(event) => setFilters({ ...filters, course_id: event.target.value })}
                  placeholder="Course UUID"
                />
              </FormField>
            </div>
            <div className="w-56">
              <FormField htmlFor="filter-department-id" label="Department ID">
                <Input
                  id="filter-department-id"
                  value={filters.department_id}
                  onChange={(event) => setFilters({ ...filters, department_id: event.target.value })}
                  placeholder="Department UUID"
                />
              </FormField>
            </div>
          </div>
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="flex justify-center p-12">
          <Spinner />
        </div>
      ) : isError || !overview ? (
        <p className="text-sm text-destructive">Failed to load analytics overview.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Marks Overview</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Result Count</span>
                <span>{overview.result_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Average Marks</span>
                <span>{formatValue(overview.average_marks)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Highest Marks</span>
                <span>{formatValue(overview.highest_marks)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Lowest Marks</span>
                <span>{formatValue(overview.lowest_marks)}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Pass / Fail</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Pass %</span>
                <span>{formatPercent(overview.pass_percentage)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Fail %</span>
                <span>{formatPercent(overview.fail_percentage)}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Confidence Distribution</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm">
              {CONFIDENCE_TIERS.map((tier) => (
                <div key={tier}>
                  <div className="flex justify-between text-xs">
                    <span className="capitalize text-muted-foreground">{tier}</span>
                    <span>{overview.confidence_distribution[tier]}</span>
                  </div>
                  <div className="mt-1 h-2 w-full rounded-full bg-secondary">
                    <div
                      className="h-2 rounded-full bg-primary"
                      style={{ width: confidenceBarWidth(overview.confidence_distribution[tier]) }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Teacher Review Signals</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Teacher Override %</span>
                <span>{formatPercent(overview.teacher_override_percentage)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Avg AI vs Teacher Difference</span>
                <span>{formatValue(overview.average_ai_vs_teacher_difference)}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Question-wise Performance</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <form onSubmit={handleLoadQuestionWise} className="flex flex-wrap items-end gap-3">
            <div className="w-64">
              <FormField htmlFor="question-exam-id" label="Exam ID" required>
                <Input
                  id="question-exam-id"
                  required
                  value={questionExamId}
                  onChange={(event) => setQuestionExamId(event.target.value)}
                  placeholder="Exam UUID"
                />
              </FormField>
            </div>
            <Button type="submit" disabled={isQuestionLoading}>
              {isQuestionLoading ? "Loading..." : "Load"}
            </Button>
          </form>

          {loadedExamId && (
            <>
              <div>
                <h3 className="mb-2 text-sm font-semibold">All Questions</h3>
                <DataTable
                  columns={questionColumns}
                  rows={questionWise?.questions ?? []}
                  getRowId={(row) => row.extracted_question_id}
                  isLoading={isQuestionLoading}
                  isError={isQuestionError}
                  emptyMessage="No question performance data found."
                />
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold">Most Difficult Questions</h3>
                <DataTable
                  columns={questionColumns}
                  rows={questionWise?.most_difficult ?? []}
                  getRowId={(row) => `difficult-${row.extracted_question_id}`}
                  isLoading={isQuestionLoading}
                  isError={isQuestionError}
                  emptyMessage="No question performance data found."
                />
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
