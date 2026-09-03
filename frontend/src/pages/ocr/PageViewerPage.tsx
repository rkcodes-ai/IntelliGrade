import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, FileText } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { getAnswerScriptPage } from "@/api/answerScriptPages";
import { listOCRResults } from "@/api/ocrResults";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { useSelectOptions } from "@/hooks/useSelectOptions";
import { cn } from "@/lib/utils";
import type { AnswerScriptPageStatus } from "@/types/ocr";

function statusBadgeClassName(status: AnswerScriptPageStatus): string {
  if (status === "ocr_complete") return "text-primary";
  if (status === "ocr_failed") return "text-destructive";
  return "text-warning";
}

function MetadataItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">{value}</dd>
    </div>
  );
}

/**
 * Read-only detail view of a single `AnswerScriptPage`. No presigned per-page
 * image URL endpoint exists yet (only `AnswerScript.download` returns a URL,
 * and that's for the original file, not a preprocessed page) — this renders
 * dimension/storage-key metadata in a placeholder box instead of an image.
 */
export function PageViewerPage() {
  const { scriptId, pageId } = useParams<{ scriptId: string; pageId: string }>();
  const navigate = useNavigate();

  const {
    data: page,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["answer-script-pages", pageId],
    queryFn: () => getAnswerScriptPage(pageId!),
    enabled: Boolean(pageId),
  });

  const { data: ocrResults } = useSelectOptions("ocr-results", () => listOCRResults({ page_size: 200 }));
  const ocrResult = ocrResults?.find((result) => result.answer_script_page_id === pageId);

  if (isLoading) {
    return (
      <div className="flex justify-center p-12">
        <Spinner />
      </div>
    );
  }

  if (isError || !page) {
    return <p className="p-6 text-sm text-muted-foreground">Page not found.</p>;
  }

  const aspectRatio = page.width_px && page.height_px ? `${page.width_px} / ${page.height_px}` : "4 / 3";

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={`Page ${page.page_number}`}
        description="Read-only detail view of an answer script page."
        actions={
          <>
            <Button variant="outline" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-4 w-4" />
              Back to script
            </Button>
            {scriptId && (
              <Button variant="outline" onClick={() => navigate(`/dashboard/answer-scripts/${scriptId}`)}>
                View Script
              </Button>
            )}
          </>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <CardTitle>Page {page.page_number}</CardTitle>
            <span
              className={cn("h-fit shrink-0 rounded-full px-2.5 py-1 text-xs font-medium", statusBadgeClassName(page.status))}
            >
              {page.status.replace(/_/g, " ")}
            </span>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <MetadataItem label="Blank Page" value={page.is_blank ? "Yes" : "No"} />
            <MetadataItem
              label="Dimensions"
              value={page.width_px != null && page.height_px != null ? `${page.width_px}x${page.height_px}` : "—"}
            />
            <MetadataItem
              label="Page Quality"
              value={
                page.quality_score != null
                  ? `${page.quality_classification ?? "—"} (${page.quality_score})`
                  : "—"
              }
            />
          </dl>

          <div
            className="flex max-w-md items-center justify-center rounded-md border border-dashed border-border bg-muted/30 text-center"
            style={{ aspectRatio }}
          >
            <div className="p-4">
              <p className="text-sm text-muted-foreground">
                {page.width_px ?? "—"} × {page.height_px ?? "—"} px
              </p>
              <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                {page.storage_key ?? "—"}
              </p>
              {page.preprocessed_storage_key && (
                <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                  {page.preprocessed_storage_key}
                </p>
              )}
              <p className="mt-3 text-xs italic text-muted-foreground">
                Image preview requires a presigned per-page URL endpoint — not yet exposed; showing metadata
                only.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {ocrResult && (
        <Card>
          <CardHeader>
            <CardTitle>OCR Result</CardTitle>
          </CardHeader>
          <CardContent>
            <Button onClick={() => navigate(`/dashboard/ocr-results/${ocrResult.id}`)}>
              <FileText className="h-4 w-4" />
              View OCR Text
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
