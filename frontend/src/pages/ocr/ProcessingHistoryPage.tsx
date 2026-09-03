import { ArrowLeft } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { listProcessingHistory } from "@/api/processingHistory";
import { DataTable, type Column } from "@/components/common/DataTable";
import { PageHeader } from "@/components/common/PageHeader";
import { PaginationControls } from "@/components/common/PaginationControls";
import { SearchInput } from "@/components/common/SearchInput";
import { Button } from "@/components/ui/button";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import type { ProcessingHistory } from "@/types/ocr";

function truncate(text: string, length = 60) {
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

/**
 * Read-only stage-transition timeline for one `AnswerScript`, server-side
 * filtered to `scriptId` — rows are written internally by pipeline/task code,
 * there is nothing to create/edit/delete here (see `api/processingHistory.ts`).
 */
export function ProcessingHistoryPage() {
  const { scriptId } = useParams<{ scriptId: string }>();
  const navigate = useNavigate();

  const list = usePaginatedList<ProcessingHistory>({
    queryKey: "processing-history",
    fetcher: (params) => listProcessingHistory({ ...params, answer_script_id: scriptId! }),
  });

  const columns: Column<ProcessingHistory>[] = [
    { key: "stage", header: "Stage", render: (row) => row.stage },
    {
      key: "transition",
      header: "From -> To",
      render: (row) => `${row.from_status ?? "—"} → ${row.to_status}`,
    },
    {
      key: "duration",
      header: "Duration",
      render: (row) => (row.duration_ms != null ? `${row.duration_ms}ms` : "—"),
    },
    { key: "triggered_by", header: "Triggered By", render: (row) => row.triggered_by },
    {
      key: "error_detail",
      header: "Error",
      render: (row) => (row.error_detail ? truncate(row.error_detail) : "—"),
    },
    { key: "created_at", header: "Timestamp", render: (row) => row.created_at },
  ];

  return (
    <div>
      <PageHeader
        title="Processing History"
        description="Stage-by-stage transition log for this answer script."
        actions={
          <Button variant="outline" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
            Back to script
          </Button>
        }
      />

      <div className="mb-4">
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search history..." />
      </div>

      <DataTable
        columns={columns}
        rows={list.items}
        getRowId={(row) => row.id}
        isLoading={list.isLoading}
        isError={list.isError}
        emptyMessage="No processing history found."
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
