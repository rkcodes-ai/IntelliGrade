import { Spinner } from "@/components/ui/spinner";

/** Full-width loading block for a single-record detail page. */
export function DetailLoading() {
  return (
    <div className="flex justify-center p-12">
      <Spinner />
    </div>
  );
}

/** "X not found." block for a single-record detail page whose record failed
 * to load or doesn't exist. Previously copy-pasted near-verbatim across
 * `OCRJobDetailsPage`, `OfficialExamDocumentDetailPage`,
 * `AnswerEvaluationDetailPage`, and similar detail screens. */
export function DetailNotFound({ message }: { message: string }) {
  return <p className="p-6 text-sm text-muted-foreground">{message}</p>;
}
