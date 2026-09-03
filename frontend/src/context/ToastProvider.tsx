import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, X, XCircle, Info } from "lucide-react";

import { cn } from "@/lib/utils";

type ToastVariant = "info" | "success" | "warning" | "error";

interface Toast {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  /** Push a toast notification. Returns nothing — fire-and-forget. */
  toast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const VARIANT_ICON: Record<ToastVariant, typeof Info> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle,
};

// Same --success/--warning/--info/--destructive tokens the Badge component
// and Dashboard KPI tiles use, so a toast and a status pill for the same
// kind of event read as the same color everywhere in the app.
const VARIANT_CLASSES: Record<ToastVariant, string> = {
  info: "border-info/30 bg-info/10 text-foreground [&_svg]:text-info",
  success: "border-success/30 bg-success/10 text-foreground [&_svg]:text-success",
  warning: "border-warning/30 bg-warning/10 text-foreground [&_svg]:text-warning",
  error: "border-destructive/30 bg-destructive/10 text-foreground [&_svg]:text-destructive",
};

/**
 * Minimal in-house toast system (no external dependency yet). Wraps the app
 * once, near the root. Real cross-cutting notifications (email/in-app/push)
 * are delivered by the future `notification/` module — this is the client
 * rendering surface for ephemeral UI feedback only.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timeoutsRef = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());

  // Auto-dismiss timers otherwise outlive an unmounted provider (e.g. a
  // mutation's toast firing after a test has torn down the tree), which
  // surfaces as a spurious "state update after unmount" error.
  useEffect(() => {
    const timeouts = timeoutsRef.current;
    return () => {
      timeouts.forEach(clearTimeout);
      timeouts.clear();
    };
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (message: string, variant: ToastVariant = "info") => {
      const id = crypto.randomUUID();
      setToasts((current) => [...current, { id, message, variant }]);
      const timeoutId = setTimeout(() => {
        timeoutsRef.current.delete(timeoutId);
        dismiss(id);
      }, 5000);
      timeoutsRef.current.add(timeoutId);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" aria-live="polite">
        {toasts.map(({ id, message, variant }) => {
          const Icon = VARIANT_ICON[variant];
          return (
            <div
              key={id}
              role="status"
              className={cn(
                "flex w-80 items-start gap-2 rounded-lg border p-3 shadow-md",
                VARIANT_CLASSES[variant],
              )}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <p className="flex-1 text-sm">{message}</p>
              <button
                onClick={() => dismiss(id)}
                aria-label="Dismiss notification"
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}
