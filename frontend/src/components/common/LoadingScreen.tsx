import { Spinner } from "@/components/ui/spinner";

export function LoadingScreen({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3">
      <Spinner className="h-8 w-8" />
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}
