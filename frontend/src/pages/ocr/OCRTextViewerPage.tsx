import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { getOCRResult, getOCRResultBlocks } from "@/api/ocrResults";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";

/**
 * Read-only viewer for a single `OCRResult`, reached from `PageViewerPage`.
 * No bounding-box overlay here — there's no renderable page image (see
 * `PageViewerPage`'s note) — just the raw/normalized text and the
 * block->line->word structure as a collapsible tree.
 */
export function OCRTextViewerPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const {
    data: result,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["ocr-results", id],
    queryFn: () => getOCRResult(id!),
    enabled: Boolean(id),
  });

  const {
    data: blocks,
    isLoading: isBlocksLoading,
    isError: isBlocksError,
  } = useQuery({
    queryKey: ["ocr-results", id, "blocks"],
    queryFn: () => getOCRResultBlocks(id!),
    enabled: Boolean(id),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center p-12">
        <Spinner />
      </div>
    );
  }

  if (isError || !result) {
    return <p className="p-6 text-sm text-muted-foreground">OCR result not found.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="OCR Text Viewer"
        description="Raw and normalized OCR text alongside the detected block/line/word structure."
        actions={
          <Button variant="outline" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
        }
      />

      <Card>
        <CardContent className="flex flex-wrap gap-6 pt-6">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Average Confidence
            </p>
            <p className="mt-0.5 text-sm">{result.average_confidence}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Language</p>
            <p className="mt-0.5 text-sm">{result.language}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Rotation Degrees
            </p>
            <p className="mt-0.5 text-sm">{result.rotation_degrees}</p>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Raw Text</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap font-mono text-sm">
              {result.raw_text}
            </pre>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Normalized Text</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap font-mono text-sm">
              {result.normalized_text ?? "Not yet normalized"}
            </pre>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Block / Line / Word Structure</CardTitle>
        </CardHeader>
        <CardContent>
          {isBlocksLoading ? (
            <div className="flex justify-center p-6">
              <Spinner />
            </div>
          ) : isBlocksError ? (
            <p className="text-sm text-destructive">Failed to load the block structure.</p>
          ) : !blocks || blocks.length === 0 ? (
            <p className="text-sm text-muted-foreground">No blocks detected for this result.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {blocks.map((block) => (
                <details key={block.id} className="rounded-md border border-border p-2">
                  <summary className="cursor-pointer text-sm font-medium">
                    {block.block_type} · confidence {block.confidence}
                  </summary>
                  <div className="mt-2 flex flex-col gap-2 pl-4">
                    {block.lines.length === 0 && (
                      <p className="text-sm text-muted-foreground">No lines in this block.</p>
                    )}
                    {block.lines.map((line) => (
                      <details key={line.id} className="rounded-md border border-border p-2">
                        <summary className="cursor-pointer text-sm">
                          {line.text} · confidence {line.confidence}
                        </summary>
                        <ul className="mt-2 flex flex-col gap-1 pl-4 text-sm text-muted-foreground">
                          {line.words.length === 0 && <li>No words in this line.</li>}
                          {line.words.map((word) => (
                            <li key={word.id}>
                              {word.text} <span className="text-xs">(confidence {word.confidence})</span>
                            </li>
                          ))}
                        </ul>
                      </details>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
