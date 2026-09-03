import { Check } from "lucide-react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

export type VerificationStep = "questions" | "model-answers" | "mark-scheme";

const STEPS: Array<{ key: VerificationStep; label: string }> = [
  { key: "questions", label: "Questions" },
  { key: "model-answers", label: "Model Answers" },
  { key: "mark-scheme", label: "Mark Scheme" },
];

interface VerificationStepNavProps {
  documentId: string;
  current: VerificationStep;
}

/**
 * Small step indicator threading the 3 teacher-verification screens for one
 * official exam document (Question Paper → Model Answer → Mark Scheme)
 * into a single visible flow. Each of the 3 pages was previously reachable
 * only via its own "Verify..." button on the document detail page, with no
 * on-screen indication that they're 3 steps of one reference-building
 * process — this makes that relationship visible without introducing a
 * new page or route (all 3 links are the existing real routes).
 */
export function VerificationStepNav({ documentId, current }: VerificationStepNavProps) {
  const currentIndex = STEPS.findIndex((step) => step.key === current);

  return (
    <nav aria-label="Verification steps" className="mb-6 flex items-center gap-2">
      {STEPS.map((step, index) => {
        const isCurrent = step.key === current;
        const isDone = index < currentIndex;
        return (
          <div key={step.key} className="flex items-center gap-2">
            {index > 0 && <div className="h-px w-6 shrink-0 bg-border" aria-hidden="true" />}
            <Link
              to={`/dashboard/official-exam-documents/${documentId}/${step.key}`}
              aria-current={isCurrent ? "step" : undefined}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                isCurrent
                  ? "border-primary bg-primary text-primary-foreground"
                  : isDone
                    ? "border-success/30 bg-success/10 text-success hover:bg-success/20"
                    : "border-border bg-secondary text-muted-foreground hover:bg-secondary/80",
              )}
            >
              {isDone ? <Check className="h-3 w-3" aria-hidden="true" /> : <span>{index + 1}</span>}
              {step.label}
            </Link>
          </div>
        );
      })}
    </nav>
  );
}
