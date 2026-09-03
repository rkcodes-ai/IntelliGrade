import { useNavigate } from "react-router-dom";

import { listUploadJobs } from "@/api/uploadJobs";
import { DataTable, type Column } from "@/components/common/DataTable";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { ProgressBar } from "@/components/common/ProgressBar";
import { SearchInput } from "@/components/common/SearchInput";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import type { UploadJob } from "@/types/ocr";

function truncateId(id: string) {
  return `${id.slice(0, 8)}…`;
}

function renderProgress(row: UploadJob) {
  if (row.total_bytes != null && row.total_bytes > 0) {
    const pct = Math.min(100, Math.round((row.bytes_received / row.total_bytes) * 100));
    return <ProgressBar percent={pct} label={`${pct}%`} className="w-32" />;
  }
  return `${row.chunks_received}/${row.total_chunks ?? "?"} chunks`;
}

/** Pure browse screen — upload jobs are created/progressed by the pipeline, never edited here. */
export function UploadQueuePage() {
  const navigate = useNavigate();

  const list = usePaginatedList<UploadJob>({
    queryKey: "upload-jobs",
    fetcher: (params) => listUploadJobs(params),
  });

  const columns: Column<UploadJob>[] = [
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
    {
      key: "status",
      header: "Status",
      render: (row) => <Badge variant={statusVariant(row.status)}>{formatStatusLabel(row.status)}</Badge>,
    },
    { key: "progress", header: "Progress", render: renderProgress },
    { key: "retry_count", header: "Retry Count", render: (row) => row.retry_count },
    {
      key: "created_at",
      header: "Created",
      render: (row) => new Date(row.created_at).toLocaleString(),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Upload Queue"
        description="Track chunked answer script uploads as they progress through the pipeline."
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search upload jobs..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No upload jobs found."
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
