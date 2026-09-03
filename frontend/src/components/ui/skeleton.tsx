import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/** Loading placeholder block — a shimmering rounded rect sized by className. */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-shimmer rounded-md bg-muted", className)}
      role="status"
      aria-label="Loading"
      {...props}
    />
  );
}
