import { useEffect, useState } from "react";

function getGreeting(hour: number): string {
  if (hour < 5) return "Good night";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  if (hour < 21) return "Good evening";
  return "Good night";
}

interface GreetingHeaderProps {
  name: string;
  institutionName?: string | null;
}

/**
 * Page-local greeting bar for the Dashboard content area — distinct from
 * the global `Topbar` (which already owns the institution switcher, theme
 * toggle, and profile/sign-out, and is shared by every other page, so it's
 * left untouched by this redesign). The clock re-renders once a minute,
 * not every second — a dashboard greeting doesn't need second-precision
 * and re-rendering the whole tree every second would be wasteful.
 */
export function GreetingHeader({ name, institutionName }: GreetingHeaderProps) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const timeLabel = now.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const dateLabel = now.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });

  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {getGreeting(now.getHours())}, {name}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {institutionName ? `${institutionName} · ` : ""}
          {dateLabel}
        </p>
      </div>
      <p className="text-sm font-medium tabular-nums text-muted-foreground">{timeLabel}</p>
    </div>
  );
}
