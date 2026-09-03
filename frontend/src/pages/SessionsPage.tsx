import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Laptop, ShieldCheck } from "lucide-react";

import { getSessions, revokeSession } from "@/api/sessions";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/context/ToastProvider";
import { extractErrorMessage } from "@/lib/errors";

export function SessionsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: sessions, isLoading } = useQuery({ queryKey: ["sessions"], queryFn: getSessions });

  const revokeMutation = useMutation({
    mutationFn: revokeSession,
    onSuccess: () => {
      toast("Session revoked.", "success");
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold">Active sessions</h1>
        <p className="text-sm text-muted-foreground">
          Devices currently signed in to your account. Revoke any you don't recognize.
        </p>
      </div>

      {isLoading && (
        <div className="flex justify-center p-8">
          <Spinner />
        </div>
      )}

      {sessions && sessions.length === 0 && (
        <p className="text-sm text-muted-foreground">No active sessions.</p>
      )}

      <div className="flex flex-col gap-3">
        {sessions?.map((session) => (
          <Card key={session.id}>
            <CardContent className="flex items-center justify-between gap-4 p-4">
              <div className="flex items-start gap-3">
                <Laptop className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                <div>
                  <p className="flex items-center gap-2 text-sm font-medium">
                    {session.device_label ?? "Unknown device"}
                    {session.is_current && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                        <ShieldCheck className="h-3 w-3" /> This device
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {session.ip_address ?? "Unknown IP"} · last active{" "}
                    {new Date(session.last_active_at).toLocaleString()}
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                disabled={revokeMutation.isPending}
                onClick={() => revokeMutation.mutate(session.id)}
              >
                Revoke
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
