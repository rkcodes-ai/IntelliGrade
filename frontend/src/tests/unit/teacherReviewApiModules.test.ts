import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { getAnalyticsOverview, getQuestionWiseAnalytics } from "@/api/analytics";
import { rejectAnswerEvaluation, rerunAnswerEvaluation } from "@/api/answerEvaluations";
import { apiClient } from "@/api/client";
import {
  approveExamResult,
  bulkApproveExamResults,
  bulkLockExamResults,
  bulkPublishExamResults,
  finalizeBatchResults,
  finalizeExamResults,
  finalizeStudentResult,
  getExamResult,
  listExamResults,
  lockExamResult,
  publishExamResult,
  unlockExamResult,
} from "@/api/examResults";
import {
  getUnreadNotificationCount,
  listMyNotifications,
  markNotificationRead,
} from "@/api/notifications";
import { downloadReport, generateReport, getReport, listReports } from "@/api/reports";
import { globalSearch } from "@/api/search";
import { getTeacherReviewDashboard, getTeacherReviewQueue } from "@/api/teacherReviewDashboard";

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(apiClient);
});

afterEach(() => {
  mock.restore();
});

const emptyPage = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };

describe("answerEvaluations api module (Module 07 additions)", () => {
  it("rejectAnswerEvaluation posts a reason to /answer-evaluations/:id/reject", async () => {
    mock.onPost("/answer-evaluations/e1/reject", { reason: "Bad match" }).reply(200, { id: "e1" });
    await expect(rejectAnswerEvaluation("e1", { reason: "Bad match" })).resolves.toEqual({
      id: "e1",
    });
  });

  it("rerunAnswerEvaluation posts to /answer-evaluations/:id/rerun", async () => {
    mock.onPost("/answer-evaluations/e1/rerun").reply(200, { id: "e1" });
    await expect(rerunAnswerEvaluation("e1")).resolves.toEqual({ id: "e1" });
  });
});

describe("examResults api module", () => {
  it("listExamResults fetches /exam-results", async () => {
    mock.onGet("/exam-results").reply(200, emptyPage);
    await expect(listExamResults()).resolves.toEqual(emptyPage);
  });

  it("getExamResult fetches /exam-results/:id", async () => {
    mock.onGet("/exam-results/r1").reply(200, { id: "r1" });
    await expect(getExamResult("r1")).resolves.toEqual({ id: "r1" });
  });

  it("finalizeStudentResult posts to /exam-results/finalize-student", async () => {
    mock
      .onPost("/exam-results/finalize-student", { exam_session_id: "s1" })
      .reply(200, { id: "r1", status: "under_review" });
    await expect(finalizeStudentResult({ exam_session_id: "s1" })).resolves.toEqual({
      id: "r1",
      status: "under_review",
    });
  });

  it("finalizeExamResults posts to /exam-results/finalize-exam", async () => {
    mock
      .onPost("/exam-results/finalize-exam", { exam_id: "ex1" })
      .reply(200, { succeeded_count: 1, failed: [] });
    await expect(finalizeExamResults({ exam_id: "ex1" })).resolves.toEqual({
      succeeded_count: 1,
      failed: [],
    });
  });

  it("finalizeBatchResults posts to /exam-results/finalize-batch", async () => {
    mock
      .onPost("/exam-results/finalize-batch", { exam_id: "ex1", batch_id: "b1" })
      .reply(200, { succeeded_count: 2, failed: [] });
    await expect(finalizeBatchResults({ exam_id: "ex1", batch_id: "b1" })).resolves.toEqual({
      succeeded_count: 2,
      failed: [],
    });
  });

  it("approveExamResult posts to /exam-results/:id/approve", async () => {
    mock.onPost("/exam-results/r1/approve").reply(200, { id: "r1", status: "approved" });
    await expect(approveExamResult("r1")).resolves.toEqual({ id: "r1", status: "approved" });
  });

  it("lockExamResult posts to /exam-results/:id/lock", async () => {
    mock.onPost("/exam-results/r1/lock").reply(200, { id: "r1", status: "locked" });
    await expect(lockExamResult("r1")).resolves.toEqual({ id: "r1", status: "locked" });
  });

  it("unlockExamResult posts to /exam-results/:id/unlock", async () => {
    mock.onPost("/exam-results/r1/unlock").reply(200, { id: "r1", status: "draft" });
    await expect(unlockExamResult("r1")).resolves.toEqual({ id: "r1", status: "draft" });
  });

  it("publishExamResult posts to /exam-results/:id/publish", async () => {
    mock.onPost("/exam-results/r1/publish").reply(200, { id: "r1", status: "published" });
    await expect(publishExamResult("r1")).resolves.toEqual({ id: "r1", status: "published" });
  });

  it("bulkApproveExamResults posts to /exam-results/bulk/approve", async () => {
    mock
      .onPost("/exam-results/bulk/approve", { exam_id: "ex1" })
      .reply(200, { succeeded_count: 3, failed: [] });
    await expect(bulkApproveExamResults({ exam_id: "ex1" })).resolves.toEqual({
      succeeded_count: 3,
      failed: [],
    });
  });

  it("bulkLockExamResults posts to /exam-results/bulk/lock", async () => {
    mock
      .onPost("/exam-results/bulk/lock", { exam_id: "ex1" })
      .reply(200, { succeeded_count: 3, failed: [] });
    await expect(bulkLockExamResults({ exam_id: "ex1" })).resolves.toEqual({
      succeeded_count: 3,
      failed: [],
    });
  });

  it("bulkPublishExamResults posts to /exam-results/bulk/publish", async () => {
    mock
      .onPost("/exam-results/bulk/publish", { exam_id: "ex1" })
      .reply(200, { succeeded_count: 3, failed: [] });
    await expect(bulkPublishExamResults({ exam_id: "ex1" })).resolves.toEqual({
      succeeded_count: 3,
      failed: [],
    });
  });
});

describe("teacherReviewDashboard api module", () => {
  it("getTeacherReviewDashboard fetches /teacher-review/dashboard", async () => {
    const summary = {
      pending_review_count: 1,
      medium_confidence_count: 2,
      low_confidence_count: 1,
      completed_reviews_count: 4,
      auto_accepted_count: 5,
    };
    mock.onGet("/teacher-review/dashboard").reply(200, summary);
    await expect(getTeacherReviewDashboard()).resolves.toEqual(summary);
  });

  it("getTeacherReviewDashboard passes filters as query params", async () => {
    mock.onGet("/teacher-review/dashboard").reply((config) => {
      expect(config.params).toEqual({ exam_id: "ex1" });
      return [200, { pending_review_count: 0, medium_confidence_count: 0, low_confidence_count: 0, completed_reviews_count: 0, auto_accepted_count: 0 }];
    });
    await getTeacherReviewDashboard({ exam_id: "ex1" });
  });

  it("getTeacherReviewQueue fetches /teacher-review/queue", async () => {
    mock.onGet("/teacher-review/queue").reply(200, emptyPage);
    await expect(getTeacherReviewQueue({ exam_id: "ex1" }, { page: 1 })).resolves.toEqual(
      emptyPage,
    );
  });
});

describe("analytics api module", () => {
  it("getAnalyticsOverview fetches /analytics/overview", async () => {
    const overview = {
      result_count: 0,
      average_marks: null,
      highest_marks: null,
      lowest_marks: null,
      pass_percentage: null,
      fail_percentage: null,
      confidence_distribution: { high: 0, medium: 0, low: 0 },
      teacher_override_percentage: null,
      average_ai_vs_teacher_difference: null,
    };
    mock.onGet("/analytics/overview").reply(200, overview);
    await expect(getAnalyticsOverview()).resolves.toEqual(overview);
  });

  it("getQuestionWiseAnalytics fetches /analytics/question-wise with exam_id param", async () => {
    const data = { questions: [], most_difficult: [] };
    mock.onGet("/analytics/question-wise").reply((config) => {
      expect(config.params).toEqual({ exam_id: "ex1" });
      return [200, data];
    });
    await expect(getQuestionWiseAnalytics("ex1")).resolves.toEqual(data);
  });
});

describe("reports api module", () => {
  it("listReports fetches /reports", async () => {
    mock.onGet("/reports").reply(200, emptyPage);
    await expect(listReports()).resolves.toEqual(emptyPage);
  });

  it("getReport fetches /reports/:id", async () => {
    mock.onGet("/reports/j1").reply(200, { id: "j1" });
    await expect(getReport("j1")).resolves.toEqual({ id: "j1" });
  });

  it("generateReport posts to /reports", async () => {
    const payload = { report_type: "institution_summary" as const, format: "csv" as const };
    mock.onPost("/reports", payload).reply(201, { id: "j1", status: "pending" });
    await expect(generateReport(payload)).resolves.toEqual({ id: "j1", status: "pending" });
  });

  it("downloadReport fetches /reports/:id/download", async () => {
    mock.onGet("/reports/j1/download").reply(200, { url: "https://example.com/file.csv" });
    await expect(downloadReport("j1")).resolves.toEqual({ url: "https://example.com/file.csv" });
  });
});

describe("search api module", () => {
  it("globalSearch fetches /search with a q param", async () => {
    const results = { query: "math", results: [] };
    mock.onGet("/search").reply((config) => {
      expect(config.params).toEqual({ q: "math" });
      return [200, results];
    });
    await expect(globalSearch("math")).resolves.toEqual(results);
  });
});

describe("notifications api module", () => {
  it("listMyNotifications fetches /notifications", async () => {
    mock.onGet("/notifications").reply(200, []);
    await expect(listMyNotifications()).resolves.toEqual([]);
  });

  it("listMyNotifications passes unread_only=true when requested", async () => {
    mock.onGet("/notifications").reply((config) => {
      expect(config.params).toEqual({ unread_only: true });
      return [200, []];
    });
    await listMyNotifications(true);
  });

  it("getUnreadNotificationCount fetches /notifications/unread-count", async () => {
    mock.onGet("/notifications/unread-count").reply(200, { unread_count: 3 });
    await expect(getUnreadNotificationCount()).resolves.toBe(3);
  });

  it("markNotificationRead posts to /notifications/:id/read", async () => {
    mock.onPost("/notifications/n1/read").reply(200, { id: "n1", is_read: true });
    await expect(markNotificationRead("n1")).resolves.toEqual({ id: "n1", is_read: true });
  });
});
