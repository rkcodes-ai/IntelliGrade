import { useState, type FormEvent } from "react";
import { Download, Plus } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { downloadReport, generateReport, listReports } from "@/api/reports";
import { DataTable, type Column } from "@/components/common/DataTable";
import { FormDialog } from "@/components/common/FormDialog";
import { FormField } from "@/components/common/FormField";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { ReportFormat, ReportJob, ReportType } from "@/types/teacherReview";

const REPORT_TYPES: ReportType[] = [
  "student",
  "question_wise",
  "teacher_review",
  "ai_performance",
  "institution_summary",
  "department_summary",
  "course_summary",
];

const REPORT_FORMATS: ReportFormat[] = ["pdf", "excel", "csv"];

function humanizeReportType(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

/**
 * Background Report Generation (Module 07, Feature 8, ADR-045). A paginated
 * list of `ReportJob` rows plus a "Generate Report" dialog. Report
 * `parameters` differ per report type (exam_id, exam_session_id, subject_id,
 * course_id, department_id, ...), so rather than building 7 dynamic forms
 * this pass takes a single free-text JSON field — see the style guide.
 */
export function ReportsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canGenerate = permissions.includes("reports:generate");

  const list = usePaginatedList<ReportJob>({
    queryKey: "reports",
    fetcher: (params) => listReports(params),
  });

  const [generateOpen, setGenerateOpen] = useState(false);
  const [reportType, setReportType] = useState<ReportType>("student");
  const [format, setFormat] = useState<ReportFormat>("pdf");
  const [parametersJson, setParametersJson] = useState("");

  const downloadMutation = useMutation({
    mutationFn: (id: string) => downloadReport(id),
    onSuccess: (result) => {
      window.open(result.url, "_blank");
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const generateMutation = useMutation({
    mutationFn: (parameters?: Record<string, unknown>) =>
      generateReport({ report_type: reportType, format, parameters }),
    onSuccess: () => {
      toast("Report generation started.", "success");
      setGenerateOpen(false);
      setReportType("student");
      setFormat("pdf");
      setParametersJson("");
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  function openGenerate() {
    setReportType("student");
    setFormat("pdf");
    setParametersJson("");
    setGenerateOpen(true);
  }

  function handleGenerateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = parametersJson.trim();
    let parameters: Record<string, unknown> | undefined;
    if (trimmed) {
      try {
        parameters = JSON.parse(trimmed) as Record<string, unknown>;
      } catch {
        toast("Parameters must be valid JSON or left blank.", "error");
        return;
      }
    }
    generateMutation.mutate(parameters);
  }

  const columns: Column<ReportJob>[] = [
    { key: "report_type", header: "Report Type", render: (row) => row.report_type.replace(/_/g, " ") },
    { key: "format", header: "Format", render: (row) => row.format.toUpperCase() },
    {
      key: "status",
      header: "Status",
      render: (row) => (
        <div>
          <Badge variant={statusVariant(row.status)}>{formatStatusLabel(row.status)}</Badge>
          {row.status === "failed" && row.failure_reason && (
            <p className="mt-0.5 text-xs text-muted-foreground">{row.failure_reason}</p>
          )}
        </div>
      ),
    },
    {
      key: "created_at",
      header: "Requested",
      render: (row) => new Date(row.created_at).toLocaleString(),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Reports"
        description="Generate and download student, question-wise, teacher review, and summary reports."
        actions={
          canGenerate && (
            <Button onClick={openGenerate}>
              <Plus className="h-4 w-4" />
              Generate Report
            </Button>
          )
        }
      />

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No reports found."
        renderActions={(row) =>
          row.status === "completed" ? (
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Download report ${row.id}`}
              disabled={downloadMutation.isPending}
              onClick={() => downloadMutation.mutate(row.id)}
            >
              <Download className="h-4 w-4" />
            </Button>
          ) : null
        }
      />

      <PaginationControls
        page={list.page}
        pageSize={list.pageSize}
        total={list.total}
        totalPages={list.totalPages}
        onPageChange={list.setPage}
        onPageSizeChange={list.setPageSize}
      />

      <FormDialog
        open={generateOpen}
        onOpenChange={setGenerateOpen}
        title="Generate Report"
        description="Reports are generated in the background — the new job will appear as pending until it completes."
        onSubmit={handleGenerateSubmit}
        isSubmitting={generateMutation.isPending}
        submitLabel="Generate"
      >
        <FormField htmlFor="report-type" label="Report Type" required>
          <Select
            id="report-type"
            required
            value={reportType}
            onChange={(event) => setReportType(event.target.value as ReportType)}
          >
            {REPORT_TYPES.map((type) => (
              <option key={type} value={type}>
                {humanizeReportType(type)}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="report-format" label="Format" required>
          <Select
            id="report-format"
            required
            value={format}
            onChange={(event) => setFormat(event.target.value as ReportFormat)}
          >
            {REPORT_FORMATS.map((value) => (
              <option key={value} value={value}>
                {value.toUpperCase()}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField htmlFor="report-parameters" label="Parameters (JSON)">
          <Input
            id="report-parameters"
            value={parametersJson}
            onChange={(event) => setParametersJson(event.target.value)}
            placeholder='{"exam_id": "..."}'
          />
        </FormField>
      </FormDialog>
    </div>
  );
}
