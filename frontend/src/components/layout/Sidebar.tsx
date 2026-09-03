import { useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";

import { cn } from "@/lib/utils";
import { useAppSelector } from "@/store";
import { DASHBOARD_ITEM, NAV_GROUPS, UTILITY_ITEMS, type NavGroup, type NavLeaf } from "@/components/layout/navConfig";

function isVisible(item: NavLeaf, permissions: string[]): boolean {
  return !item.requiredPermissions || item.requiredPermissions.every((p) => permissions.includes(p));
}

function groupContainsPath(group: NavGroup, pathname: string): boolean {
  return group.items.some((item) => pathname === item.to || pathname.startsWith(`${item.to}/`));
}

/**
 * Workflow-oriented sidebar (Module 12 IA redesign): the same set of real
 * routes/permissions as before, regrouped into collapsible sections that
 * mirror IntelliGrade's actual evaluation pipeline (Evaluation Packages →
 * Student Answer Scripts → AI Evaluation → Teacher Review → Results →
 * Reports & Analytics), with Administration and the de-emphasized
 * Academic & Assessment Setup entities (owned by the Exam Cell, not part
 * of IntelliGrade's own workflow) below. See `navConfig.ts` for the full
 * mapping and the design notes on where a requested concept doesn't map
 * to a distinct real route.
 */
export function Sidebar() {
  const collapsed = useAppSelector((state) => state.ui.sidebarCollapsed);
  const permissions = useAppSelector((state) => state.auth.user?.permissions ?? []);
  const location = useLocation();

  const visibleGroups = useMemo(
    () =>
      NAV_GROUPS.map((group) => ({
        ...group,
        items: group.items.filter((item) => isVisible(item, permissions)),
      })).filter((group) => group.items.length > 0),
    [permissions],
  );
  const visibleUtilityItems = useMemo(
    () => UTILITY_ITEMS.filter((item) => isVisible(item, permissions)),
    [permissions],
  );

  const [expanded, setExpanded] = useState<Set<string>>(
    () => new Set(NAV_GROUPS.filter((g) => !g.defaultCollapsed).map((g) => g.id)),
  );

  function toggleGroup(id: string) {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function isGroupOpen(group: NavGroup): boolean {
    return expanded.has(group.id) || groupContainsPath(group, location.pathname);
  }

  const linkClassName = ({ isActive }: { isActive: boolean }) =>
    cn(
      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150",
      isActive
        ? "bg-primary text-primary-foreground shadow-soft"
        : "text-muted-foreground hover:bg-secondary hover:text-foreground",
    );

  // Icon-collapsed sidebar: flatten to a single icon column (no group
  // headers/disclosure — a flyout submenu system is a bigger change than
  // this IA redesign's scope). Matches the pre-redesign collapsed behavior.
  if (collapsed) {
    const flatItems: NavLeaf[] = [
      DASHBOARD_ITEM,
      ...visibleGroups.flatMap((group) => group.items),
      ...visibleUtilityItems,
    ];
    return (
      <aside className="flex w-14 flex-col gap-0.5 overflow-y-auto border-r border-border bg-card p-2">
        {flatItems.map(({ label, to, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} title={label} className={linkClassName}>
            <Icon className="h-4 w-4 shrink-0" />
            <span className="sr-only">{label}</span>
          </NavLink>
        ))}
      </aside>
    );
  }

  return (
    <aside className="flex w-64 flex-col gap-1 overflow-y-auto border-r border-border bg-card p-2">
      <NavLink to={DASHBOARD_ITEM.to} end={DASHBOARD_ITEM.end} className={linkClassName}>
        <DASHBOARD_ITEM.icon className="h-4 w-4 shrink-0" />
        <span className="truncate">{DASHBOARD_ITEM.label}</span>
      </NavLink>

      <div className="my-1 border-t border-border" />

      {visibleGroups.map((group) => {
        const open = isGroupOpen(group);
        const GroupIcon = group.icon;
        return (
          <div key={group.id}>
            <button
              type="button"
              onClick={() => toggleGroup(group.id)}
              aria-expanded={open}
              title={group.label}
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-semibold leading-tight text-foreground transition-colors duration-150 hover:bg-secondary"
            >
              <GroupIcon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="flex-1">{group.label}</span>
              <ChevronDown
                className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200", open && "rotate-180")}
                aria-hidden="true"
              />
            </button>
            <div
              className="grid transition-[grid-template-rows] duration-200 ease-out"
              style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
            >
              <div className="overflow-hidden">
                <div className="flex flex-col gap-0.5 py-0.5 pl-4">
                  {group.items.map(({ label, to, icon: Icon, end }) => (
                    <NavLink key={to} to={to} end={end} className={linkClassName}>
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="truncate">{label}</span>
                    </NavLink>
                  ))}
                </div>
              </div>
            </div>
          </div>
        );
      })}

      {visibleUtilityItems.length > 0 && (
        <>
          <div className="my-1 border-t border-border" />
          {visibleUtilityItems.map(({ label, to, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={linkClassName}>
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{label}</span>
            </NavLink>
          ))}
        </>
      )}
    </aside>
  );
}
