import { Link } from "react-router-dom";
import type { LucideIcon } from "lucide-react";

interface QuickActionCardProps {
  label: string;
  description: string;
  icon: LucideIcon;
  to: string;
}

/** One tile in the Quick Actions grid — a large, obviously-clickable shortcut. */
export function QuickActionCard({ label, description, icon: Icon, to }: QuickActionCardProps) {
  return (
    <Link
      to={to}
      className="group flex flex-col gap-2 rounded-xl border border-border bg-card p-4 shadow-soft transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-soft-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <span className="text-sm font-semibold text-foreground">{label}</span>
      <span className="text-xs text-muted-foreground">{description}</span>
    </Link>
  );
}
