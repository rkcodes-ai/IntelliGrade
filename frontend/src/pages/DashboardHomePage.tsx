import {
  AlertTriangle,
  BarChart3,
  Bell,
  CheckCircle2,
  Clock,
  FileBarChart2,
  FileSearch2,
  Gauge,
  HeartPulse,
  Inbox,
  ListChecks,
  ScanText,
  Sparkles,
  UploadCloud,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { GreetingHeader } from "@/components/dashboard/GreetingHeader";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { EmptyState, ListItem, ListSkeleton } from "@/components/dashboard/ListItem";
import { MiniBarChart } from "@/components/dashboard/MiniBarChart";
import { MiniDonut } from "@/components/dashboard/MiniDonut";
import { QuickActionCard } from "@/components/dashboard/QuickActionCard";
import { SectionCard } from "@/components/dashboard/SectionCard";
import { formatStatusLabel, statusVariant } from "@/lib/statusStyles";
import { formatRelativeTime } from "@/lib/formatRelativeTime";
import { useMyInstitutions } from "@/hooks/useMyInstitutions";
import {
  useDashboardAnalytics,
  useDashboardHealth,
  useDashboardNotifications,
  useDashboardOcrJobs,
  useDashboardRecentEvaluations,
  useDashboardReports,
  useDashboardTeacherReviewSummary,
  useDashboardUploadJobs,
} from "@/hooks/useDashboardData";
import { useAppSelector } from "@/store";

function hasPermission(permissions: string[], code: string): boolean {
  return permissions.includes(code);
}

function formatMinutes(minutes: number | null): string {
  if (minutes === null) return "—";
  if (minutes < 1) return "<1m";
  if (minutes < 60) return `${Math.round(minutes)}m`;
  return `${(minutes / 60).toFixed(1)}h`;
}

function formatSeconds(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.round(seconds / 60)}m`;
}

/**
 * The Dashboard — IntelliGrade's Decision Center. Every widget is backed by
 * real, already-existing endpoints (analytics, teacher review, OCR jobs,
 * upload jobs, reports, notifications, health) via `useDashboardData`
 * hooks; nothing here is mocked or fabricated. Widgets are gated on the
 * signed-in user's real permission codes (mirroring `Sidebar`'s
 * `NAV_ITEMS`), since — unlike every other route — the dashboard index
 * route has no `PermissionGuard` around it and must defend itself.
 */
export function DashboardHomePage() {
  const user = useAppSelector((state) => state.auth.user);
  const permissions = user?.permissions ?? [];
  const institutionsQuery = useMyInstitutions();
  const currentInstitutionId = useAppSelector((state) => state.institution.currentInstitutionId);
  const currentInstitution = institutionsQuery.data?.find((inst) => inst.id === currentInstitutionId);

  const canReview = hasPermission(permissions, "teacher_review_dashboard:read");
  const canOcr = hasPermission(permissions, "ocr_jobs:read");
  const canAnalytics = hasPermission(permissions, "analytics:read");
  const canUploads = hasPermission(permissions, "upload_jobs:read");
  const canReports = hasPermission(permissions, "reports:read");
  const canNotifications = hasPermission(permissions, "notifications:read");
  const canCreateOfficialDocs = hasPermission(permissions, "official_exam_documents:create");
  const canCreateAnswerScripts = hasPermission(permissions, "answer_scripts:create");

  const health = useDashboardHealth();
  const reviewSummary = useDashboardTeacherReviewSummary(canReview);
  const evaluations = useDashboardRecentEvaluations(canReview);
  const analytics = useDashboardAnalytics(canAnalytics);
  const ocrJobs = useDashboardOcrJobs(canOcr);
  const uploadJobs = useDashboardUploadJobs(canUploads);
  const reports = useDashboardReports(canReports);
  const notifications = useDashboardNotifications(canNotifications);

  const highConfidence = analytics.data?.confidence_distribution.high ?? 0;
  const mediumConfidence = analytics.data?.confidence_distribution.medium ?? 0;
  const lowConfidence = analytics.data?.confidence_distribution.low ?? 0;
  const confidenceTotal = highConfidence + mediumConfidence + lowConfidence;
  const highConfidencePct = confidenceTotal > 0 ? Math.round((highConfidence / confidenceTotal) * 100) : null;

  const aiQueueCount = (reviewSummary.data?.medium_confidence_count ?? 0) + (reviewSummary.data?.low_confidence_count ?? 0);

  // "Pending Actions": real signals synthesized from data already fetched
  // for other widgets — items that genuinely need a human to act, not a
  // separate backend concept of its own.
  const pendingActions = [
    canReview && (reviewSummary.data?.low_confidence_count ?? 0) > 0 && {
      key: "low-confidence",
      label: `${reviewSummary.data?.low_confidence_count} low-confidence evaluation${reviewSummary.data?.low_confidence_count === 1 ? "" : "s"} need review`,
      to: "/dashboard/teacher-review",
      tone: "danger" as const,
    },
    canOcr && (ocrJobs.data?.recent.some((job) => job.status === "failed") ?? false) && {
      key: "ocr-failed",
      label: "One or more OCR jobs failed and may need a retry",
      to: "/dashboard/ocr-status",
      tone: "warning" as const,
    },
    canReports && (reports.data?.items.some((job) => job.status === "failed") ?? false) && {
      key: "report-failed",
      label: "A report generation job failed",
      to: "/dashboard/reports",
      tone: "warning" as const,
    },
    canUploads && (uploadJobs.data?.items.some((job) => job.status === "failed") ?? false) && {
      key: "upload-failed",
      label: "A student answer script upload failed",
      to: "/dashboard/upload-queue",
      tone: "warning" as const,
    },
  ].filter(Boolean) as Array<{ key: string; label: string; to: string; tone: "danger" | "warning" }>;

  return (
    <div className="flex flex-col gap-6">
      <GreetingHeader name={user?.full_name ?? "there"} institutionName={currentInstitution?.name} />

      {/* AI Insight Bar */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-7">
        {canReview && (
          <KpiCard
            label="Pending Reviews"
            value={reviewSummary.data?.pending_review_count ?? 0}
            icon={ListChecks}
            tone="warning"
            to="/dashboard/teacher-review"
            isLoading={reviewSummary.isLoading}
          />
        )}
        {canOcr && (
          <KpiCard
            label="OCR Queue"
            value={ocrJobs.data?.queued ?? 0}
            icon={ScanText}
            tone="info"
            to="/dashboard/ocr-status"
            isLoading={ocrJobs.isLoading}
            hint={ocrJobs.data ? `of last ${ocrJobs.data.sampleSize} jobs` : undefined}
          />
        )}
        {canReview && (
          <KpiCard
            label="AI Queue"
            value={aiQueueCount}
            icon={Sparkles}
            tone="primary"
            to="/dashboard/teacher-review"
            isLoading={reviewSummary.isLoading}
            hint="Medium + low confidence"
          />
        )}
        {canReview && (
          <KpiCard
            label="Completed Today"
            value={evaluations.data?.completedToday ?? 0}
            icon={CheckCircle2}
            tone="success"
            to="/dashboard/answer-evaluations"
            isLoading={evaluations.isLoading}
          />
        )}
        {canAnalytics && (
          <KpiCard
            label="Avg. Confidence"
            value={highConfidencePct !== null ? `${highConfidencePct}%` : "—"}
            icon={Gauge}
            tone="info"
            to="/dashboard/analytics"
            isLoading={analytics.isLoading}
            hint="Share rated high-confidence"
          />
        )}
        {canReview && (
          <KpiCard
            label="Avg. Eval. Time"
            value={formatMinutes(evaluations.data?.avgTurnaroundMinutes ?? null)}
            icon={Clock}
            tone="neutral"
            isLoading={evaluations.isLoading}
            hint="Created → evaluated"
          />
        )}
        <KpiCard
          label="System Health"
          value={health.data?.status === "ok" ? "Operational" : health.isError ? "Unreachable" : "Checking"}
          icon={HeartPulse}
          tone={health.data?.status === "ok" ? "success" : health.isError ? "danger" : "neutral"}
          isLoading={health.isLoading}
          hint={health.data?.environment}
        />
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          {canReview && (
            <SectionCard title="AI Evaluation Timeline" icon={Sparkles} viewAllTo="/dashboard/answer-evaluations">
              {evaluations.isLoading ? (
                <ListSkeleton />
              ) : evaluations.data && evaluations.data.recent.length > 0 ? (
                <div className="flex flex-col gap-1">
                  {evaluations.data.recent.map((item) => (
                    <ListItem
                      key={item.id}
                      icon={Sparkles}
                      iconTone={item.confidence_tier === "low" ? "danger" : item.confidence_tier === "medium" ? "warning" : "success"}
                      title={`Question ${item.extracted_question_id.slice(0, 8)} · ${item.suggested_marks ?? "—"} / ${item.max_marks} marks`}
                      subtitle={`Confidence: ${item.confidence_tier ?? "unrated"}`}
                      meta={formatRelativeTime(item.created_at)}
                      trailing={<Badge variant={statusVariant(item.review_status)}>{formatStatusLabel(item.review_status)}</Badge>}
                    />
                  ))}
                </div>
              ) : (
                <EmptyState message="No AI evaluations yet." />
              )}
            </SectionCard>
          )}

          {canOcr && (
            <SectionCard title="OCR Processing Status" icon={ScanText} viewAllTo="/dashboard/ocr-status">
              {ocrJobs.isLoading ? (
                <ListSkeleton />
              ) : ocrJobs.data && ocrJobs.data.recent.length > 0 ? (
                <div className="flex flex-col gap-1">
                  {ocrJobs.data.recent.map((job) => (
                    <ListItem
                      key={job.id}
                      icon={ScanText}
                      iconTone={job.status === "failed" ? "danger" : job.status === "completed" ? "success" : "info"}
                      title={`Answer script ${job.answer_script_id.slice(0, 8)}`}
                      subtitle={job.error_message ?? undefined}
                      meta={formatRelativeTime(job.created_at)}
                      trailing={<Badge variant={statusVariant(job.status)}>{formatStatusLabel(job.status)}</Badge>}
                    />
                  ))}
                </div>
              ) : (
                <EmptyState message="No OCR jobs yet." />
              )}
            </SectionCard>
          )}

          {canReview && (
            <SectionCard title="Teacher Review Queue" icon={ListChecks} viewAllTo="/dashboard/teacher-review">
              {evaluations.isLoading ? (
                <ListSkeleton />
              ) : evaluations.data && evaluations.data.pending.length > 0 ? (
                <div className="flex flex-col gap-1">
                  {evaluations.data.pending.slice(0, 5).map((item) => (
                    <ListItem
                      key={item.id}
                      icon={ListChecks}
                      iconTone="warning"
                      title={`Question ${item.extracted_question_id.slice(0, 8)}`}
                      subtitle={`Suggested ${item.suggested_marks ?? "—"} / ${item.max_marks} marks`}
                      meta={formatRelativeTime(item.created_at)}
                      trailing={<Badge variant={statusVariant(item.review_status)}>{formatStatusLabel(item.review_status)}</Badge>}
                    />
                  ))}
                </div>
              ) : (
                <EmptyState message="Nothing awaiting review right now." />
              )}
            </SectionCard>
          )}

          <SectionCard title="Pending Actions" icon={AlertTriangle}>
            {pendingActions.length > 0 ? (
              <div className="flex flex-col gap-1">
                {pendingActions.map((action) => (
                  <ListItem
                    key={action.key}
                    icon={AlertTriangle}
                    iconTone={action.tone}
                    title={action.label}
                    onClick={() => {
                      window.location.assign(action.to);
                    }}
                  />
                ))}
              </div>
            ) : (
              <EmptyState message="Nothing needs your attention. Nice work." />
            )}
          </SectionCard>
        </div>

        <div className="flex flex-col gap-4">
          <SectionCard title="Quick Actions">
            <div className="grid grid-cols-2 gap-3">
              {canCreateOfficialDocs && (
                <QuickActionCard
                  label="Upload Official Documents"
                  description="Question paper, model answer, mark scheme"
                  icon={FileSearch2}
                  to="/dashboard/official-exam-documents"
                />
              )}
              {canCreateAnswerScripts && (
                <QuickActionCard
                  label="Upload Student Scripts"
                  description="Add answer scripts for OCR"
                  icon={UploadCloud}
                  to="/dashboard/answer-scripts"
                />
              )}
              {canOcr && (
                <QuickActionCard
                  label="OCR Status"
                  description="Monitor digitization jobs"
                  icon={ScanText}
                  to="/dashboard/ocr-status"
                />
              )}
              {canReview && (
                <QuickActionCard
                  label="Teacher Review"
                  description="Confirm or override AI marks"
                  icon={ListChecks}
                  to="/dashboard/teacher-review"
                />
              )}
              {canReports && (
                <QuickActionCard
                  label="Generate Reports"
                  description="Student, class, or institution"
                  icon={FileBarChart2}
                  to="/dashboard/reports"
                />
              )}
              {canAnalytics && (
                <QuickActionCard
                  label="Analytics"
                  description="Performance across cohorts"
                  icon={BarChart3}
                  to="/dashboard/analytics"
                />
              )}
            </div>
          </SectionCard>

          {canReports && (
            <SectionCard title="Recent Reports" icon={FileBarChart2} viewAllTo="/dashboard/reports">
              {reports.isLoading ? (
                <ListSkeleton rows={3} />
              ) : reports.data && reports.data.items.length > 0 ? (
                <div className="flex flex-col gap-1">
                  {reports.data.items.map((job) => (
                    <ListItem
                      key={job.id}
                      icon={FileBarChart2}
                      iconTone={job.status === "failed" ? "danger" : job.status === "completed" ? "success" : "info"}
                      title={formatStatusLabel(job.report_type)}
                      subtitle={job.format.toUpperCase()}
                      meta={formatRelativeTime(job.created_at)}
                      trailing={<Badge variant={statusVariant(job.status)}>{formatStatusLabel(job.status)}</Badge>}
                    />
                  ))}
                </div>
              ) : (
                <EmptyState message="No reports generated yet." />
              )}
            </SectionCard>
          )}

          {canUploads && (
            <SectionCard title="Recent Uploads" icon={UploadCloud} viewAllTo="/dashboard/upload-queue">
              {uploadJobs.isLoading ? (
                <ListSkeleton rows={3} />
              ) : uploadJobs.data && uploadJobs.data.items.length > 0 ? (
                <div className="flex flex-col gap-1">
                  {uploadJobs.data.items.map((job) => {
                    const pct =
                      job.total_bytes && job.total_bytes > 0
                        ? Math.round((job.bytes_received / job.total_bytes) * 100)
                        : null;
                    return (
                      <ListItem
                        key={job.id}
                        icon={UploadCloud}
                        iconTone={job.status === "failed" ? "danger" : job.status === "completed" ? "success" : "info"}
                        title={`Script ${job.answer_script_id.slice(0, 8)}`}
                        subtitle={pct !== null ? `${pct}% received` : undefined}
                        meta={formatRelativeTime(job.created_at)}
                        trailing={<Badge variant={statusVariant(job.status)}>{formatStatusLabel(job.status)}</Badge>}
                      />
                    );
                  })}
                </div>
              ) : (
                <EmptyState message="No uploads yet." />
              )}
            </SectionCard>
          )}

          {canNotifications && (
            <SectionCard title="System Notifications" icon={Bell} viewAllTo="/dashboard/notifications">
              {notifications.isLoading ? (
                <ListSkeleton rows={3} />
              ) : notifications.data && notifications.data.length > 0 ? (
                <div className="flex flex-col gap-1">
                  {notifications.data.slice(0, 5).map((notification) => (
                    <ListItem
                      key={notification.id}
                      icon={Bell}
                      iconTone="primary"
                      title={formatStatusLabel(notification.event_type)}
                      meta={formatRelativeTime(notification.created_at)}
                    />
                  ))}
                </div>
              ) : (
                <EmptyState message="You're all caught up." />
              )}
            </SectionCard>
          )}
        </div>
      </div>

      {/* Analytics */}
      {canAnalytics && (
        <SectionCard title="Analytics" icon={BarChart3} viewAllTo="/dashboard/analytics" viewAllLabel="Full analytics">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">Confidence Distribution</p>
              {analytics.data ? (
                <MiniDonut
                  segments={[
                    { label: "High", value: highConfidence, colorVar: "--success" },
                    { label: "Medium", value: mediumConfidence, colorVar: "--warning" },
                    { label: "Low", value: lowConfidence, colorVar: "--destructive" },
                  ]}
                  centerValue={confidenceTotal > 0 ? String(confidenceTotal) : "0"}
                  centerLabel="results"
                />
              ) : (
                <Skeleton className="h-28 w-full" />
              )}
            </div>
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">Pass / Fail Rate</p>
              <p className="text-2xl font-semibold tabular-nums text-success">{analytics.data?.pass_percentage ?? "—"}%</p>
              <p className="text-xs text-muted-foreground">passing · {analytics.data?.fail_percentage ?? "—"}% failing</p>
              <p className="mt-3 text-xs font-medium text-muted-foreground">Completion Rate</p>
              <p className="text-2xl font-semibold tabular-nums">
                {reviewSummary.data
                  ? `${Math.round(
                      (reviewSummary.data.completed_reviews_count /
                        Math.max(1, reviewSummary.data.completed_reviews_count + reviewSummary.data.pending_review_count)) *
                        100,
                    )}%`
                  : "—"}
              </p>
            </div>
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">Processing Time</p>
              <p className="text-xs text-muted-foreground">Avg. OCR job</p>
              <p className="text-xl font-semibold tabular-nums">{formatSeconds(ocrJobs.data?.avgDurationSeconds ?? null)}</p>
              <p className="mt-2 text-xs text-muted-foreground">Avg. AI evaluation</p>
              <p className="text-xl font-semibold tabular-nums">{formatMinutes(evaluations.data?.avgTurnaroundMinutes ?? null)}</p>
              <p className="mt-2 text-xs text-muted-foreground">OCR success rate</p>
              <p className="text-xl font-semibold tabular-nums">{ocrJobs.data?.successRate ?? "—"}%</p>
            </div>
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">Daily Evaluation Trend (last 7 days)</p>
              {evaluations.data ? (
                <MiniBarChart data={evaluations.data.dailyTrend} colorVar="--chart-1" />
              ) : (
                <Skeleton className="h-24 w-full" />
              )}
            </div>
          </div>
        </SectionCard>
      )}

      {!canReview && !canOcr && !canAnalytics && !canUploads && !canReports && !canNotifications && (
        <SectionCard title="Welcome to IntelliGrade" icon={Inbox}>
          <EmptyState message="Your role doesn't have access to any dashboard widgets yet. Contact an administrator if you believe this is incorrect." />
        </SectionCard>
      )}
    </div>
  );
}
