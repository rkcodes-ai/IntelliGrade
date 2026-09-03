import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { aiConfigurationsApi } from "@/api/aiConfigurations";
import { getAIProvider, listAIProviders, updateAIProvider } from "@/api/aiProviders";
import {
  confirmAnswerEvaluation,
  getAnswerEvaluation,
  listAnswerEvaluations,
  overrideAnswerEvaluation,
  triggerAnswerEvaluation,
} from "@/api/answerEvaluations";
import { apiClient } from "@/api/client";
import {
  getExtractedModelAnswer,
  listExtractedModelAnswers,
  updateExtractedModelAnswer,
  verifyExtractedModelAnswer,
} from "@/api/extractedModelAnswers";
import {
  getExtractedQuestion,
  listExtractedQuestions,
  updateExtractedQuestion,
  verifyExtractedQuestion,
} from "@/api/extractedQuestions";
import {
  expandMarkScheme,
  getMarkSchemeRange,
  listMarkSchemeRanges,
  updateMarkSchemeRange,
  verifyMarkSchemeRange,
} from "@/api/markSchemeRanges";
import {
  cancelOfficialExamDocument,
  downloadOfficialExamDocument,
  getOfficialExamDocument,
  listDeletedOfficialExamDocuments,
  listOfficialExamDocuments,
  removeOfficialExamDocument,
  restoreOfficialExamDocument,
  retryOfficialExamDocument,
  updateOfficialExamDocument,
  uploadOfficialExamDocument,
} from "@/api/officialExamDocuments";
import {
  getOfficialExamDocumentPage,
  listOfficialExamDocumentPages,
} from "@/api/officialExamDocumentPages";

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(apiClient);
});

afterEach(() => {
  mock.restore();
});

const emptyPage = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };

describe("officialExamDocuments api module", () => {
  it("listOfficialExamDocuments fetches /official-exam-documents", async () => {
    mock.onGet("/official-exam-documents").reply(200, emptyPage);
    await expect(listOfficialExamDocuments()).resolves.toEqual(emptyPage);
  });

  it("listDeletedOfficialExamDocuments fetches /official-exam-documents/deleted", async () => {
    mock.onGet("/official-exam-documents/deleted").reply(200, emptyPage);
    await expect(listDeletedOfficialExamDocuments()).resolves.toEqual(emptyPage);
  });

  it("getOfficialExamDocument fetches /official-exam-documents/:id", async () => {
    mock.onGet("/official-exam-documents/d1").reply(200, { id: "d1" });
    await expect(getOfficialExamDocument("d1")).resolves.toEqual({ id: "d1" });
  });

  it("uploadOfficialExamDocument posts multipart form data with exam_id and document_type", async () => {
    mock.onPost("/official-exam-documents").reply((config) => {
      expect(config.headers?.["Content-Type"]).toBe("multipart/form-data");
      const form = config.data as FormData;
      expect(form.get("exam_id")).toBe("exam1");
      expect(form.get("document_type")).toBe("question_paper");
      return [201, { id: "d1" }];
    });
    const file = new File(["content"], "qp.pdf", { type: "application/pdf" });
    await expect(
      uploadOfficialExamDocument("exam1", "question_paper", file),
    ).resolves.toEqual({ id: "d1" });
  });

  it("uploadOfficialExamDocument includes allow_duplicate when requested", async () => {
    mock.onPost("/official-exam-documents").reply((config) => {
      const form = config.data as FormData;
      expect(form.get("allow_duplicate")).toBe("true");
      return [201, { id: "d1" }];
    });
    const file = new File(["content"], "qp.pdf", { type: "application/pdf" });
    await expect(
      uploadOfficialExamDocument("exam1", "question_paper", file, { allowDuplicate: true }),
    ).resolves.toEqual({ id: "d1" });
  });

  it("updateOfficialExamDocument patches /official-exam-documents/:id", async () => {
    mock.onPatch("/official-exam-documents/d1").reply(200, { id: "d1", is_active: false });
    await expect(updateOfficialExamDocument("d1", { is_active: false })).resolves.toEqual({
      id: "d1",
      is_active: false,
    });
  });

  it("removeOfficialExamDocument deletes /official-exam-documents/:id", async () => {
    mock.onDelete("/official-exam-documents/d1").reply(204);
    await expect(removeOfficialExamDocument("d1")).resolves.toBeUndefined();
  });

  it("restoreOfficialExamDocument posts to /official-exam-documents/:id/restore", async () => {
    mock.onPost("/official-exam-documents/d1/restore").reply(200, { id: "d1" });
    await expect(restoreOfficialExamDocument("d1")).resolves.toEqual({ id: "d1" });
  });

  it("retryOfficialExamDocument posts to /official-exam-documents/:id/retry", async () => {
    mock.onPost("/official-exam-documents/d1/retry").reply(200, { id: "d1", ocr_status: "stored" });
    await expect(retryOfficialExamDocument("d1")).resolves.toEqual({ id: "d1", ocr_status: "stored" });
  });

  it("cancelOfficialExamDocument posts to /official-exam-documents/:id/cancel", async () => {
    mock
      .onPost("/official-exam-documents/d1/cancel")
      .reply(200, { id: "d1", ocr_status: "cancelled" });
    await expect(cancelOfficialExamDocument("d1")).resolves.toEqual({
      id: "d1",
      ocr_status: "cancelled",
    });
  });

  it("downloadOfficialExamDocument fetches /official-exam-documents/:id/download", async () => {
    mock.onGet("/official-exam-documents/d1/download").reply(200, { url: "http://example.test/d1" });
    await expect(downloadOfficialExamDocument("d1")).resolves.toEqual({
      url: "http://example.test/d1",
    });
  });
});

describe("officialExamDocumentPages api module", () => {
  it("listOfficialExamDocumentPages fetches /official-exam-document-pages", async () => {
    mock.onGet("/official-exam-document-pages").reply(200, emptyPage);
    await expect(listOfficialExamDocumentPages()).resolves.toEqual(emptyPage);
  });

  it("getOfficialExamDocumentPage fetches /official-exam-document-pages/:id", async () => {
    mock.onGet("/official-exam-document-pages/p1").reply(200, { id: "p1" });
    await expect(getOfficialExamDocumentPage("p1")).resolves.toEqual({ id: "p1" });
  });
});

describe("extractedQuestions api module", () => {
  it("listExtractedQuestions fetches /extracted-questions", async () => {
    mock.onGet("/extracted-questions").reply(200, emptyPage);
    await expect(listExtractedQuestions()).resolves.toEqual(emptyPage);
  });

  it("getExtractedQuestion fetches /extracted-questions/:id", async () => {
    mock.onGet("/extracted-questions/q1").reply(200, { id: "q1" });
    await expect(getExtractedQuestion("q1")).resolves.toEqual({ id: "q1" });
  });

  it("updateExtractedQuestion patches /extracted-questions/:id", async () => {
    mock.onPatch("/extracted-questions/q1").reply(200, { id: "q1", question_text: "Updated" });
    await expect(updateExtractedQuestion("q1", { question_text: "Updated" })).resolves.toEqual({
      id: "q1",
      question_text: "Updated",
    });
  });

  it("verifyExtractedQuestion posts to /extracted-questions/:id/verify", async () => {
    mock.onPost("/extracted-questions/q1/verify").reply(200, { id: "q1", verification_status: "verified" });
    await expect(verifyExtractedQuestion("q1")).resolves.toEqual({
      id: "q1",
      verification_status: "verified",
    });
  });
});

describe("extractedModelAnswers api module", () => {
  it("listExtractedModelAnswers fetches /extracted-model-answers", async () => {
    mock.onGet("/extracted-model-answers").reply(200, emptyPage);
    await expect(listExtractedModelAnswers()).resolves.toEqual(emptyPage);
  });

  it("getExtractedModelAnswer fetches /extracted-model-answers/:id", async () => {
    mock.onGet("/extracted-model-answers/a1").reply(200, { id: "a1" });
    await expect(getExtractedModelAnswer("a1")).resolves.toEqual({ id: "a1" });
  });

  it("updateExtractedModelAnswer patches /extracted-model-answers/:id", async () => {
    mock.onPatch("/extracted-model-answers/a1").reply(200, { id: "a1" });
    await expect(updateExtractedModelAnswer("a1", { answer_text: "Updated" })).resolves.toEqual({
      id: "a1",
    });
  });

  it("verifyExtractedModelAnswer posts to /extracted-model-answers/:id/verify", async () => {
    mock.onPost("/extracted-model-answers/a1/verify").reply(200, { id: "a1" });
    await expect(verifyExtractedModelAnswer("a1")).resolves.toEqual({ id: "a1" });
  });
});

describe("markSchemeRanges api module", () => {
  it("listMarkSchemeRanges fetches /mark-scheme-ranges", async () => {
    mock.onGet("/mark-scheme-ranges").reply(200, emptyPage);
    await expect(listMarkSchemeRanges()).resolves.toEqual(emptyPage);
  });

  it("getMarkSchemeRange fetches /mark-scheme-ranges/:id", async () => {
    mock.onGet("/mark-scheme-ranges/r1").reply(200, { id: "r1" });
    await expect(getMarkSchemeRange("r1")).resolves.toEqual({ id: "r1" });
  });

  it("updateMarkSchemeRange patches /mark-scheme-ranges/:id", async () => {
    mock.onPatch("/mark-scheme-ranges/r1").reply(200, { id: "r1" });
    await expect(updateMarkSchemeRange("r1", { marks_per_question: 2 })).resolves.toEqual({
      id: "r1",
    });
  });

  it("verifyMarkSchemeRange posts to /mark-scheme-ranges/:id/verify", async () => {
    mock.onPost("/mark-scheme-ranges/r1/verify").reply(200, { id: "r1" });
    await expect(verifyMarkSchemeRange("r1")).resolves.toEqual({ id: "r1" });
  });

  it("expandMarkScheme fetches /mark-scheme-ranges/expand with document_id param", async () => {
    mock.onGet("/mark-scheme-ranges/expand").reply((config) => {
      expect(config.params).toEqual({ document_id: "doc1" });
      return [200, { marks_by_question: { "1": "1.00", "2": "1.00" }, warnings: [] }];
    });
    await expect(expandMarkScheme("doc1")).resolves.toEqual({
      marks_by_question: { "1": "1.00", "2": "1.00" },
      warnings: [],
    });
  });
});

describe("aiProviders api module", () => {
  it("listAIProviders fetches /ai-providers", async () => {
    mock.onGet("/ai-providers").reply(200, emptyPage);
    await expect(listAIProviders()).resolves.toEqual(emptyPage);
  });

  it("getAIProvider fetches /ai-providers/:id", async () => {
    mock.onGet("/ai-providers/p1").reply(200, { id: "p1" });
    await expect(getAIProvider("p1")).resolves.toEqual({ id: "p1" });
  });

  it("updateAIProvider patches /ai-providers/:id", async () => {
    mock.onPatch("/ai-providers/p1").reply(200, { id: "p1", is_enabled: true });
    await expect(updateAIProvider("p1", { is_enabled: true })).resolves.toEqual({
      id: "p1",
      is_enabled: true,
    });
  });
});

describe("aiConfigurations api module (createCrudApi)", () => {
  it("covers list/get/create/update/remove/restore/listDeleted", async () => {
    mock.onGet("/ai-configurations").reply(200, emptyPage);
    await expect(aiConfigurationsApi.list()).resolves.toEqual(emptyPage);

    mock.onGet("/ai-configurations/deleted").reply(200, emptyPage);
    await expect(aiConfigurationsApi.listDeleted()).resolves.toEqual(emptyPage);

    mock.onGet("/ai-configurations/c1").reply(200, { id: "c1" });
    await expect(aiConfigurationsApi.get("c1")).resolves.toEqual({ id: "c1" });

    mock.onPost("/ai-configurations").reply(201, { id: "c1" });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- generic payload shape, irrelevant to path coverage
    await expect(aiConfigurationsApi.create({} as any)).resolves.toEqual({ id: "c1" });

    mock.onPatch("/ai-configurations/c1").reply(200, { id: "c1" });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- generic payload shape, irrelevant to path coverage
    await expect(aiConfigurationsApi.update("c1", {} as any)).resolves.toEqual({ id: "c1" });

    mock.onDelete("/ai-configurations/c1").reply(204);
    await expect(aiConfigurationsApi.remove("c1")).resolves.toBeUndefined();

    mock.onPost("/ai-configurations/c1/restore").reply(200, { id: "c1" });
    await expect(aiConfigurationsApi.restore("c1")).resolves.toEqual({ id: "c1" });
  });
});

describe("answerEvaluations api module", () => {
  it("listAnswerEvaluations fetches /answer-evaluations", async () => {
    mock.onGet("/answer-evaluations").reply(200, emptyPage);
    await expect(listAnswerEvaluations()).resolves.toEqual(emptyPage);
  });

  it("getAnswerEvaluation fetches /answer-evaluations/:id", async () => {
    mock.onGet("/answer-evaluations/e1").reply(200, { id: "e1" });
    await expect(getAnswerEvaluation("e1")).resolves.toEqual({ id: "e1" });
  });

  it("triggerAnswerEvaluation posts to /answer-evaluations", async () => {
    mock.onPost("/answer-evaluations").reply(201, { id: "e1" });
    await expect(
      triggerAnswerEvaluation({ exam_session_id: "s1", extracted_question_id: "q1" }),
    ).resolves.toEqual({ id: "e1" });
  });

  it("confirmAnswerEvaluation posts to /answer-evaluations/:id/confirm", async () => {
    mock.onPost("/answer-evaluations/e1/confirm").reply(200, { id: "e1", review_status: "teacher_confirmed" });
    await expect(confirmAnswerEvaluation("e1")).resolves.toEqual({
      id: "e1",
      review_status: "teacher_confirmed",
    });
  });

  it("overrideAnswerEvaluation posts to /answer-evaluations/:id/override", async () => {
    mock.onPost("/answer-evaluations/e1/override").reply(200, { id: "e1", final_marks: "7.50" });
    await expect(
      overrideAnswerEvaluation("e1", { final_marks: 7.5, notes: "Partial credit" }),
    ).resolves.toEqual({ id: "e1", final_marks: "7.50" });
  });
});
