import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getUnreadNotificationCount,
  listMyNotifications,
  markNotificationRead,
} from "@/api/notifications";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/context/ToastProvider";
import { extractErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import type { NotificationEvent } from "@/types/teacherReview";

function humanizeEventType(eventType: string): string {
  return eventType.replace(/_/g, " ");
}

function NotificationCard({
  notification,
  onMarkRead,
  isMarkingRead,
}: {
  notification: NotificationEvent;
  onMarkRead: (id: string) => void;
  isMarkingRead: boolean;
}) {
  const payloadEntries = Object.entries(notification.payload ?? {});

  return (
    <Card
      className={cn(
        "border-l-4",
        notification.is_read ? "border-l-transparent" : "border-l-primary bg-secondary/50",
      )}
    >
      <CardContent className="flex items-start justify-between gap-4 p-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium capitalize">
              {humanizeEventType(notification.event_type)}
            </span>
            {!notification.is_read && (
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                Unread
              </span>
            )}
          </div>
          <span className="text-xs text-muted-foreground">
            {new Date(notification.created_at).toLocaleString()}
          </span>
          {payloadEntries.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
              {payloadEntries.map(([key, value]) => (
                <span key={key}>
                  {key}: {String(value)}
                </span>
              ))}
            </div>
          )}
        </div>
        {!notification.is_read && (
          <Button
            variant="outline"
            size="sm"
            disabled={isMarkingRead}
            onClick={() => onMarkRead(notification.id)}
          >
            {isMarkingRead ? "Marking..." : "Mark as read"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Notifications screen (Module 07, Feature 10, ADR-046): a simple, non-paginated
 * list of the current user's `NotificationEvent` rows, with an All / Unread
 * Only toggle and a mark-as-read action per row.
 */
export function NotificationsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [unreadOnly, setUnreadOnly] = useState(false);

  const {
    data: notifications,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["notifications", unreadOnly],
    queryFn: () => listMyNotifications(unreadOnly),
  });

  const { data: unreadCount } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => getUnreadNotificationCount(),
  });

  const markReadMutation = useMutation({
    mutationFn: (id: string) => markNotificationRead(id),
    onSuccess: () => {
      toast("Notification marked as read.", "success");
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (error) => toast(extractErrorMessage(error), "error"),
  });

  const rows = notifications ?? [];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Notifications"
        description={
          unreadCount != null
            ? `You have ${unreadCount} unread notification${unreadCount === 1 ? "" : "s"}.`
            : undefined
        }
      />

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant={!unreadOnly ? "default" : "outline"}
          size="sm"
          onClick={() => setUnreadOnly(false)}
        >
          All
        </Button>
        <Button
          type="button"
          variant={unreadOnly ? "default" : "outline"}
          size="sm"
          onClick={() => setUnreadOnly(true)}
        >
          Unread Only
        </Button>
      </div>

      {isLoading && (
        <div className="flex justify-center p-12">
          <Spinner />
        </div>
      )}

      {!isLoading && isError && (
        <p className="text-sm text-muted-foreground">Failed to load notifications.</p>
      )}

      {!isLoading && !isError && rows.length === 0 && (
        <p className="text-sm text-muted-foreground">No notifications yet.</p>
      )}

      {!isLoading && !isError && rows.length > 0 && (
        <div className="flex flex-col gap-3">
          {rows.map((notification) => (
            <NotificationCard
              key={notification.id}
              notification={notification}
              onMarkRead={(id) => markReadMutation.mutate(id)}
              isMarkingRead={
                markReadMutation.isPending && markReadMutation.variables === notification.id
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
