import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Ban } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { cancelOCRJob, getOCRJob } from "@/api/ocrJobs";
import { listOCRProviders } from "@/api/ocrProviders";
import { DetailLoading, DetailNotFound } from "@/components/common/DetailState";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/context/ToastProvider";
import { useSelectOptions } from "@/hooks/useSelectOptions";
import { extractErrorMessage } from "@/lib/errors";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { useAppSelector } from "@/store";
import type { OCRJobStatus } from "@/types/ocr";

const CANCELLABLE_STATUSES: OCRJobStatus[] = ["queued", "running"];

function MetadataItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">{value}</dd>
    </div>
  );
}

/**
 * Read-only detail view of a single `OCRJob`, reached from
 * `OCRStatusDashboardPage`'s row-level "Details" action. Only additional
 * workflow action is Cancel — everything else about a job is pipeline-managed.
 */
export function OCRJobDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const canCancel = permissions.includes("ocr_jobs:cancel");

  const {
    data: job,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["ocr-jobs", id],
    queryFn: () => getOCRJob(id!),
    enabled: Boolean(id),
  });

  const { data: providers } = useSelectOptions("ocr-providers", () => listOCRProviders({ page_size: 200 }));
  const providerName = (providerId: string) =>
    providers?.find((provider) => provider.id === providerId)?.name ?? providerId;

  const cancelMutation = useMutation({
    mutationFn: () => cancelOCRJob(id!),
    onSuccess: () => {
      toast("OCR job cancelled.", "success");
      void queryClient.invalidateQueries({ queryKey: ["ocr-jobs", id] });
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  if (isLoading) {
    return <DetailLoading />;
  }

  if (isError || !job) {
    return <DetailNotFound message="OCR job not found." />;
  }

  const canCancelJob = canCancel && CANCELLABLE_STATUSES.includes(job.status);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="OCR Job Details"
        description="Metadata and status for a single OCR processing job."
        actions={
          <>
            {canCancelJob && (
              <Button
                variant="destructive"
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
              >
                <Ban className="h-4 w-4" />
                Cancel
              </Button>
            )}
            <Button variant="outline" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-4 w-4" />
              Back
            </Button>
          </>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <CardTitle>Job {job.id}</CardTitle>
            <Badge variant={statusVariant(job.status)} className="h-fit shrink-0">
              {formatStatusLabel(job.status)}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {job.error_message && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {job.error_message}
            </div>
          )}
          {job.requested_ocr_provider_id && (
            <div className="rounded-md border border-warning/50 bg-warning/10 p-3 text-sm">
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-warning">
                Provider Fallback
              </p>
              <p>
                Requested <strong>{providerName(job.requested_ocr_provider_id)}</strong>, fell back to{" "}
                <strong>{providerName(job.ocr_provider_id)}</strong>.
              </p>
              {job.fallback_reason && (
                <p className="mt-1 text-muted-foreground">{job.fallback_reason}</p>
              )}
            </div>
          )}
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <MetadataItem label="Provider" value={providerName(job.ocr_provider_id)} />
            <MetadataItem label="Priority" value={job.priority} />
            <MetadataItem label="Retries" value={`${job.retry_count}/${job.max_retries}`} />
            <MetadataItem
              label="Celery Task ID"
              value={<span className="font-mono text-xs">{job.celery_task_id ?? "—"}</span>}
            />
            <MetadataItem label="Started At" value={job.started_at ?? "—"} />
            <MetadataItem label="Completed At" value={job.completed_at ?? "—"} />
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
