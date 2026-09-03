import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { alternativeAnswersApi } from "@/api/alternativeAnswers";
import { answerKeysApi } from "@/api/answerKeys";
import { assessmentConfigurationsApi } from "@/api/assessmentConfigurations";
import { assessmentStatusesApi } from "@/api/assessmentStatuses";
import { assessmentTypesApi } from "@/api/assessmentTypes";
import { assessmentsApi } from "@/api/assessments";
import { bloomTaxonomyLevelsApi } from "@/api/bloomTaxonomyLevels";
import { apiClient } from "@/api/client";
import { difficultyLevelsApi } from "@/api/difficultyLevels";
import { evaluationConfigurationsApi } from "@/api/evaluationConfigurations";
import { createEvaluationHistory, getEvaluationHistory, listEvaluationHistory } from "@/api/evaluationHistory";
import { examInstructionsApi } from "@/api/examInstructions";
import { examSchedulesApi } from "@/api/examSchedules";
import { examSessionsApi } from "@/api/examSessions";
import { examsApi } from "@/api/exams";
import { expectedConceptsApi } from "@/api/expectedConcepts";
import { expectedKeywordsApi } from "@/api/expectedKeywords";
import { markDistributionsApi } from "@/api/markDistributions";
import { modelAnswersApi } from "@/api/modelAnswers";
import { getQuestionApproval, listQuestionApprovals } from "@/api/questionApprovals";
import { questionBlueprintSectionsApi } from "@/api/questionBlueprintSections";
import { questionBlueprintsApi } from "@/api/questionBlueprints";
import { questionCategoriesApi } from "@/api/questionCategories";
import { questionPaperQuestionMappingsApi } from "@/api/questionPaperQuestionMappings";
import { questionPaperSectionsApi } from "@/api/questionPaperSections";
import { questionPaperTemplatesApi } from "@/api/questionPaperTemplates";
import {
  approveQuestionPaper,
  createQuestionPaperVersionSnapshot,
  questionPapersApi,
  rejectQuestionPaper,
  submitQuestionPaperForReview,
} from "@/api/questionPapers";
import { getQuestionPaperVersion, listQuestionPaperVersions } from "@/api/questionPaperVersions";
import { questionReviewsApi } from "@/api/questionReviews";
import { questionTagsApi } from "@/api/questionTags";
import { questionTypesApi } from "@/api/questionTypes";
import {
  addQuestionTag,
  approveQuestion,
  createQuestionVersionSnapshot,
  questionsApi,
  rejectQuestion,
  removeQuestionTag,
  submitQuestionForReview,
} from "@/api/questions";
import {
  getQuestionVersion,
  listDeletedQuestionVersions,
  listQuestionVersions,
  removeQuestionVersion,
  restoreQuestionVersion,
} from "@/api/questionVersions";
import { randomizationStrategiesApi } from "@/api/randomizationStrategies";
import { referenceNotesApi } from "@/api/referenceNotes";
import { rubricCriteriaApi } from "@/api/rubricCriteria";
import { rubricsApi } from "@/api/rubrics";

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(apiClient);
});

afterEach(() => {
  mock.restore();
});

const emptyPage = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };

describe("assessment entity api modules resolve to the correct backend paths", () => {
  it.each([
    ["alternativeAnswers", alternativeAnswersApi, "/alternative-answers"],
    ["answerKeys", answerKeysApi, "/answer-keys"],
    ["assessmentConfigurations", assessmentConfigurationsApi, "/assessment-configurations"],
    ["assessmentStatuses", assessmentStatusesApi, "/assessment-statuses"],
    ["assessmentTypes", assessmentTypesApi, "/assessment-types"],
    ["assessments", assessmentsApi, "/assessments"],
    ["bloomTaxonomyLevels", bloomTaxonomyLevelsApi, "/bloom-taxonomy-levels"],
    ["difficultyLevels", difficultyLevelsApi, "/difficulty-levels"],
    ["evaluationConfigurations", evaluationConfigurationsApi, "/evaluation-configurations"],
    ["examInstructions", examInstructionsApi, "/exam-instructions"],
    ["examSchedules", examSchedulesApi, "/exam-schedules"],
    ["examSessions", examSessionsApi, "/exam-sessions"],
    ["exams", examsApi, "/exams"],
    ["expectedConcepts", expectedConceptsApi, "/expected-concepts"],
    ["expectedKeywords", expectedKeywordsApi, "/expected-keywords"],
    ["markDistributions", markDistributionsApi, "/mark-distributions"],
    ["modelAnswers", modelAnswersApi, "/model-answers"],
    ["questionBlueprintSections", questionBlueprintSectionsApi, "/question-blueprint-sections"],
    ["questionBlueprints", questionBlueprintsApi, "/question-blueprints"],
    ["questionCategories", questionCategoriesApi, "/question-categories"],
    [
      "questionPaperQuestionMappings",
      questionPaperQuestionMappingsApi,
      "/question-paper-question-mappings",
    ],
    ["questionPaperSections", questionPaperSectionsApi, "/question-paper-sections"],
    ["questionPaperTemplates", questionPaperTemplatesApi, "/question-paper-templates"],
    ["questionPapers", questionPapersApi, "/question-papers"],
    ["questionReviews", questionReviewsApi, "/question-reviews"],
    ["questionTags", questionTagsApi, "/question-tags"],
    ["questionTypes", questionTypesApi, "/question-types"],
    ["questions", questionsApi, "/questions"],
    ["randomizationStrategies", randomizationStrategiesApi, "/randomization-strategies"],
    ["referenceNotes", referenceNotesApi, "/reference-notes"],
    ["rubricCriteria", rubricCriteriaApi, "/rubric-criteria"],
    ["rubrics", rubricsApi, "/rubrics"],
  ] as const)("%s.list hits %s", async (_name, api, path) => {
    mock.onGet(path).reply(200, emptyPage);
    const result = await api.list();
    expect(result).toEqual(emptyPage);
  });

  it.each([
    ["alternativeAnswers", alternativeAnswersApi, "/alternative-answers"],
    ["answerKeys", answerKeysApi, "/answer-keys"],
    ["assessmentConfigurations", assessmentConfigurationsApi, "/assessment-configurations"],
    ["assessmentStatuses", assessmentStatusesApi, "/assessment-statuses"],
    ["assessmentTypes", assessmentTypesApi, "/assessment-types"],
    ["assessments", assessmentsApi, "/assessments"],
    ["bloomTaxonomyLevels", bloomTaxonomyLevelsApi, "/bloom-taxonomy-levels"],
    ["difficultyLevels", difficultyLevelsApi, "/difficulty-levels"],
    ["evaluationConfigurations", evaluationConfigurationsApi, "/evaluation-configurations"],
    ["examInstructions", examInstructionsApi, "/exam-instructions"],
    ["examSchedules", examSchedulesApi, "/exam-schedules"],
    ["examSessions", examSessionsApi, "/exam-sessions"],
    ["exams", examsApi, "/exams"],
    ["expectedConcepts", expectedConceptsApi, "/expected-concepts"],
    ["expectedKeywords", expectedKeywordsApi, "/expected-keywords"],
    ["markDistributions", markDistributionsApi, "/mark-distributions"],
    ["modelAnswers", modelAnswersApi, "/model-answers"],
    ["questionBlueprintSections", questionBlueprintSectionsApi, "/question-blueprint-sections"],
    ["questionBlueprints", questionBlueprintsApi, "/question-blueprints"],
    ["questionCategories", questionCategoriesApi, "/question-categories"],
    [
      "questionPaperQuestionMappings",
      questionPaperQuestionMappingsApi,
      "/question-paper-question-mappings",
    ],
    ["questionPaperSections", questionPaperSectionsApi, "/question-paper-sections"],
    ["questionPaperTemplates", questionPaperTemplatesApi, "/question-paper-templates"],
    ["questionPapers", questionPapersApi, "/question-papers"],
    ["questionReviews", questionReviewsApi, "/question-reviews"],
    ["questionTags", questionTagsApi, "/question-tags"],
    ["questionTypes", questionTypesApi, "/question-types"],
    ["questions", questionsApi, "/questions"],
    ["randomizationStrategies", randomizationStrategiesApi, "/randomization-strategies"],
    ["referenceNotes", referenceNotesApi, "/reference-notes"],
    ["rubricCriteria", rubricCriteriaApi, "/rubric-criteria"],
    ["rubrics", rubricsApi, "/rubrics"],
  ] as const)("%s covers get/create/update/remove/restore/listDeleted", async (_name, api, path) => {
    mock.onGet(`${path}/deleted`).reply(200, emptyPage);
    await expect(api.listDeleted()).resolves.toEqual(emptyPage);

    mock.onGet(`${path}/e1`).reply(200, { id: "e1" });
    await expect(api.get("e1")).resolves.toEqual({ id: "e1" });

    mock.onPost(path).reply(201, { id: "e1" });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- generic payload shape varies per entity, irrelevant to path coverage
    await expect(api.create({} as any)).resolves.toEqual({ id: "e1" });

    mock.onPatch(`${path}/e1`).reply(200, { id: "e1" });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- generic payload shape varies per entity, irrelevant to path coverage
    await expect(api.update("e1", {} as any)).resolves.toEqual({ id: "e1" });

    mock.onDelete(`${path}/e1`).reply(204);
    await expect(api.remove("e1")).resolves.toBeUndefined();

    mock.onPost(`${path}/e1/restore`).reply(200, { id: "e1" });
    await expect(api.restore("e1")).resolves.toEqual({ id: "e1" });
  });
});

describe("questions api extras", () => {
  it("submitQuestionForReview posts to /questions/:id/submit-for-review", async () => {
    mock.onPost("/questions/q1/submit-for-review").reply(200, { id: "q1" });
    await expect(submitQuestionForReview("q1")).resolves.toEqual({ id: "q1" });
  });

  it("approveQuestion posts to /questions/:id/approve", async () => {
    mock.onPost("/questions/q1/approve").reply(200, { id: "q1" });
    await expect(approveQuestion("q1")).resolves.toEqual({ id: "q1" });
  });

  it("rejectQuestion posts a reason to /questions/:id/reject", async () => {
    mock.onPost("/questions/q1/reject").reply((config) => {
      expect(JSON.parse(config.data as string)).toEqual({ reason: "Needs work" });
      return [200, { id: "q1" }];
    });
    await expect(rejectQuestion("q1", { reason: "Needs work" })).resolves.toEqual({ id: "q1" });
  });

  it("addQuestionTag posts to /questions/:id/tags", async () => {
    mock.onPost("/questions/q1/tags").reply(201, { id: "map1", tag_id: "t1" });
    await expect(addQuestionTag("q1", { tag_id: "t1" })).resolves.toEqual({ id: "map1", tag_id: "t1" });
  });

  it("removeQuestionTag deletes /questions/:id/tags/:tagId", async () => {
    mock.onDelete("/questions/q1/tags/t1").reply(204);
    await expect(removeQuestionTag("q1", "t1")).resolves.toBeUndefined();
  });

  it("createQuestionVersionSnapshot posts to /questions/:id/versions", async () => {
    mock.onPost("/questions/q1/versions").reply(201, { id: "v1", version_number: 2 });
    await expect(createQuestionVersionSnapshot("q1", { change_reason: "Fixed typo" })).resolves.toEqual({
      id: "v1",
      version_number: 2,
    });
  });
});

describe("questionPapers api extras", () => {
  it("submitQuestionPaperForReview posts to /question-papers/:id/submit-for-review", async () => {
    mock.onPost("/question-papers/p1/submit-for-review").reply(200, { id: "p1" });
    await expect(submitQuestionPaperForReview("p1")).resolves.toEqual({ id: "p1" });
  });

  it("approveQuestionPaper posts to /question-papers/:id/approve", async () => {
    mock.onPost("/question-papers/p1/approve").reply(200, { id: "p1" });
    await expect(approveQuestionPaper("p1")).resolves.toEqual({ id: "p1" });
  });

  it("rejectQuestionPaper posts a reason to /question-papers/:id/reject", async () => {
    mock.onPost("/question-papers/p1/reject").reply(200, { id: "p1" });
    await expect(rejectQuestionPaper("p1", { reason: "Incomplete" })).resolves.toEqual({ id: "p1" });
  });

  it("createQuestionPaperVersionSnapshot posts to /question-papers/:id/versions", async () => {
    mock.onPost("/question-papers/p1/versions").reply(201, { id: "v1" });
    await expect(
      createQuestionPaperVersionSnapshot("p1", { change_reason: "Reordered sections" }),
    ).resolves.toEqual({ id: "v1" });
  });
});

describe("read-only history/approval api modules", () => {
  it("listEvaluationHistory fetches /evaluation-history", async () => {
    mock.onGet("/evaluation-history").reply(200, emptyPage);
    await expect(listEvaluationHistory()).resolves.toEqual(emptyPage);
  });

  it("getEvaluationHistory fetches /evaluation-history/:id", async () => {
    mock.onGet("/evaluation-history/h1").reply(200, { id: "h1" });
    await expect(getEvaluationHistory("h1")).resolves.toEqual({ id: "h1" });
  });

  it("createEvaluationHistory posts to /evaluation-history", async () => {
    mock.onPost("/evaluation-history").reply(201, { id: "h1" });
    await expect(createEvaluationHistory({ exam_session_id: "s1" })).resolves.toEqual({ id: "h1" });
  });

  it("listQuestionApprovals fetches /question-approvals", async () => {
    mock.onGet("/question-approvals").reply(200, emptyPage);
    await expect(listQuestionApprovals()).resolves.toEqual(emptyPage);
  });

  it("getQuestionApproval fetches /question-approvals/:id", async () => {
    mock.onGet("/question-approvals/a1").reply(200, { id: "a1" });
    await expect(getQuestionApproval("a1")).resolves.toEqual({ id: "a1" });
  });

  it("listQuestionPaperVersions fetches /question-paper-versions", async () => {
    mock.onGet("/question-paper-versions").reply(200, emptyPage);
    await expect(listQuestionPaperVersions()).resolves.toEqual(emptyPage);
  });

  it("getQuestionPaperVersion fetches /question-paper-versions/:id", async () => {
    mock.onGet("/question-paper-versions/v1").reply(200, { id: "v1" });
    await expect(getQuestionPaperVersion("v1")).resolves.toEqual({ id: "v1" });
  });

  it("listQuestionVersions fetches /question-versions", async () => {
    mock.onGet("/question-versions").reply(200, emptyPage);
    await expect(listQuestionVersions()).resolves.toEqual(emptyPage);
  });

  it("listDeletedQuestionVersions fetches /question-versions/deleted", async () => {
    mock.onGet("/question-versions/deleted").reply(200, emptyPage);
    await expect(listDeletedQuestionVersions()).resolves.toEqual(emptyPage);
  });

  it("getQuestionVersion fetches /question-versions/:id", async () => {
    mock.onGet("/question-versions/v1").reply(200, { id: "v1" });
    await expect(getQuestionVersion("v1")).resolves.toEqual({ id: "v1" });
  });

  it("removeQuestionVersion deletes /question-versions/:id", async () => {
    mock.onDelete("/question-versions/v1").reply(204);
    await expect(removeQuestionVersion("v1")).resolves.toBeUndefined();
  });

  it("restoreQuestionVersion posts to /question-versions/:id/restore", async () => {
    mock.onPost("/question-versions/v1/restore").reply(200, { id: "v1" });
    await expect(restoreQuestionVersion("v1")).resolves.toEqual({ id: "v1" });
  });
});
