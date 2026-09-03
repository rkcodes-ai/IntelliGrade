import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Eye } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { cancelOCRJob, listOCRJobs } from "@/api/ocrJobs";
import { listOCRProviders } from "@/api/ocrProviders";
import { DataTable, type Column } from "@/components/common/DataTable";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { SearchInput } from "@/components/common/SearchInput";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/context/ToastProvider";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { useSelectOptions } from "@/hooks/useSelectOptions";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { OCRJob, OCRJobStatus } from "@/types/ocr";

function truncateId(id: string) {
  return `${id.slice(0, 8)}…`;
}

/** Title-cases a status label for tile headings/filter buttons (badges
 * elsewhere in the app intentionally stay lowercase — see `statusStyles.ts`). */
function titleCase(label: string): string {
  return label.replace(/\b\w/g, (char) => char.toUpperCase());
}

const CANCELLABLE_STATUSES: OCRJobStatus[] = ["queued", "running"];

/** Statuses summarized as tiles above the table — computed from the
 * bounded recent sample below, same convention as the Dashboard's OCR
 * widgets (there is no server-side status-count endpoint to aggregate
 * across the entire table instead). */
const SUMMARY_STATUSES: OCRJobStatus[] = ["queued", "running", "completed", "failed"];
const STATUS_FILTER_OPTIONS: Array<OCRJobStatus | "all"> = [
  "all",
  "queued",
  "running",
  "completed",
  "failed",
  "cancelled",
];
const RECENT_SAMPLE_SIZE = 200;

/** Cancel is the only mutable action here — everything else is pipeline-managed. */
export function OCRStatusDashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCancel = permissions.includes("ocr_jobs:cancel");
  const institutionId = useAppSelector((state) => state.institution.currentInstitutionId);

  const [statusFilter, setStatusFilter] = useState<OCRJobStatus | "all">("all");

  const list = usePaginatedList<OCRJob>({
    queryKey: "ocr-jobs",
    fetcher: (params) => listOCRJobs(params),
  });
  const { data: providers } = useSelectOptions("ocr-providers", () => listOCRProviders({ page_size: 200 }));

  // Backend has no status-filter or status-count query param (see
  // `api/ocrJobs.ts`) — a bounded recent sample drives both the summary
  // tiles and the client-side status filter, same pattern already used by
  // `EvaluationReviewDashboardPage`'s confidence-tier tabs.
  const recentSample = useQuery({
    queryKey: ["ocr-jobs-recent-sample", institutionId],
    queryFn: () => listOCRJobs({ page: 1, page_size: RECENT_SAMPLE_SIZE, sort_by: "created_at", sort_order: "desc" }),
    enabled: Boolean(institutionId),
  });

  const summaryCounts = useMemo(() => {
    const items = recentSample.data?.items ?? [];
    const counts: Partial<Record<OCRJobStatus, number>> = {};
    for (const status of SUMMARY_STATUSES) {
      counts[status] = items.filter((job) => job.status === status).length;
    }
    return counts;
  }, [recentSample.data]);

  const filteredItems = useMemo(
    () => (statusFilter === "all" ? list.items : list.items.filter((job) => job.status === statusFilter)),
    [list.items, statusFilter],
  );

  const cancelMutation = useMutation({
    mutationFn: (id: string) => cancelOCRJob(id),
    onSuccess: () => {
      toast("OCR job cancelled.", "success");
      void queryClient.invalidateQueries({ queryKey: ["ocr-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["ocr-jobs-recent-sample"] });
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const providerName = (id: string) => providers?.find((provider) => provider.id === id)?.name ?? id;

  const columns: Column<OCRJob>[] = [
    {
      key: "answer_script_id",
      header: "Answer Script",
      render: (row) => (
        <Button
          variant="ghost"
          size="sm"
          className="h-auto p-0 font-mono text-xs underline"
          onClick={() => navigate(`/dashboard/answer-scripts/${row.answer_script_id}`)}
        >
          {truncateId(row.answer_script_id)}
        </Button>
      ),
    },
    { key: "provider", header: "Provider", render: (row) => providerName(row.ocr_provider_id) },
    {
      key: "status",
      header: "Status",
      render: (row) => <Badge variant={statusVariant(row.status)}>{formatStatusLabel(row.status)}</Badge>,
    },
    { key: "priority", header: "Priority", render: (row) => row.priority },
    { key: "retries", header: "Retries", render: (row) => `${row.retry_count}/${row.max_retries}` },
    {
      key: "started_at",
      header: "Started",
      render: (row) => (row.started_at ? new Date(row.started_at).toLocaleString() : "—"),
    },
    {
      key: "completed_at",
      header: "Completed",
      render: (row) => (row.completed_at ? new Date(row.completed_at).toLocaleString() : "—"),
    },
  ];

  return (
    <div>
      <PageHeader
        title="OCR Status Dashboard"
        description="Monitor OCR jobs as they queue, run, and complete across providers."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {SUMMARY_STATUSES.map((status) => (
          <Card key={status}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {titleCase(formatStatusLabel(status))}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold tabular-nums">{summaryCounts[status] ?? "—"}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search OCR jobs..." />
        <div className="flex flex-wrap gap-1">
          {STATUS_FILTER_OPTIONS.map((status) => (
            <Button
              key={status}
              type="button"
              size="sm"
              variant={statusFilter === status ? "default" : "outline"}
              onClick={() => setStatusFilter(status)}
            >
              {status === "all" ? "All" : titleCase(formatStatusLabel(status))}
            </Button>
          ))}
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={filteredItems}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No OCR jobs found."
        renderActions={(row) => (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`View OCR job ${truncateId(row.id)}`}
              onClick={() => navigate(`/dashboard/ocr-jobs/${row.id}`)}
            >
              <Eye className="h-4 w-4" />
            </Button>
            {canCancel && CANCELLABLE_STATUSES.includes(row.status) && (
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Cancel OCR job ${truncateId(row.id)}`}
                disabled={cancelMutation.isPending}
                onClick={() => cancelMutation.mutate(row.id)}
              >
                <Ban className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      />

      <PaginationControls
        page={list.page}
        pageSize={list.pageSize}
        total={list.total}
        totalPages={list.totalPages}
        onPageChange={list.setPage}
        onPageSizeChange={list.setPageSize}
      />
    </div>
  );
}
