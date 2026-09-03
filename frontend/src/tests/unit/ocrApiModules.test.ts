import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  bulkUploadAnswerScripts,
  cancelAnswerScript,
  downloadAnswerScript,
  getAnswerScript,
  listAnswerScripts,
  listDeletedAnswerScripts,
  removeAnswerScript,
  restoreAnswerScript,
  retryAnswerScript,
  updateAnswerScript,
  uploadAnswerScript,
} from "@/api/answerScripts";
import { getAnswerScriptPage, listAnswerScriptPages } from "@/api/answerScriptPages";
import { apiClient } from "@/api/client";
import { ocrConfigurationsApi } from "@/api/ocrConfigurations";
import { cancelOCRJob, createOCRJob, getOCRJob, listOCRJobs } from "@/api/ocrJobs";
import { getOCRProvider, listOCRProviders, updateOCRProvider } from "@/api/ocrProviders";
import {
  getOCRResult,
  getOCRResultBlocks,
  listOCRBlocks,
  listOCRLines,
  listOCRResults,
  listOCRWords,
} from "@/api/ocrResults";
import { getProcessingHistory, listProcessingHistory } from "@/api/processingHistory";
import { getUploadJob, listUploadJobs } from "@/api/uploadJobs";

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(apiClient);
});

afterEach(() => {
  mock.restore();
});

const emptyPage = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };

describe("answerScripts api module", () => {
  it("listAnswerScripts fetches /answer-scripts", async () => {
    mock.onGet("/answer-scripts").reply(200, emptyPage);
    await expect(listAnswerScripts()).resolves.toEqual(emptyPage);
  });

  it("listDeletedAnswerScripts fetches /answer-scripts/deleted", async () => {
    mock.onGet("/answer-scripts/deleted").reply(200, emptyPage);
    await expect(listDeletedAnswerScripts()).resolves.toEqual(emptyPage);
  });

  it("getAnswerScript fetches /answer-scripts/:id", async () => {
    mock.onGet("/answer-scripts/s1").reply(200, { id: "s1" });
    await expect(getAnswerScript("s1")).resolves.toEqual({ id: "s1" });
  });

  it("uploadAnswerScript posts multipart form data", async () => {
    mock.onPost("/answer-scripts").reply((config) => {
      expect(config.headers?.["Content-Type"]).toBe("multipart/form-data");
      expect(config.data).toBeInstanceOf(FormData);
      return [201, { id: "s1" }];
    });
    const file = new File(["content"], "script.pdf", { type: "application/pdf" });
    await expect(uploadAnswerScript("exam1", file)).resolves.toEqual({ id: "s1" });
  });

  it("uploadAnswerScript includes allow_duplicate when requested", async () => {
    mock.onPost("/answer-scripts").reply((config) => {
      const form = config.data as FormData;
      expect(form.get("allow_duplicate")).toBe("true");
      return [201, { id: "s1" }];
    });
    const file = new File(["content"], "script.pdf", { type: "application/pdf" });
    await expect(
      uploadAnswerScript("exam1", file, { allowDuplicate: true }),
    ).resolves.toEqual({ id: "s1" });
  });

  it("bulkUploadAnswerScripts posts multipart form data with multiple files", async () => {
    mock.onPost("/answer-scripts/bulk").reply(201, { created: 2, errors: [] });
    const files = [
      new File(["a"], "a.pdf", { type: "application/pdf" }),
      new File(["b"], "b.pdf", { type: "application/pdf" }),
    ];
    await expect(bulkUploadAnswerScripts("exam1", files)).resolves.toEqual({
      created: 2,
      errors: [],
    });
  });

  it("updateAnswerScript patches /answer-scripts/:id", async () => {
    mock.onPatch("/answer-scripts/s1").reply(200, { id: "s1", is_active: false });
    await expect(updateAnswerScript("s1", { is_active: false })).resolves.toEqual({
      id: "s1",
      is_active: false,
    });
  });

  it("removeAnswerScript deletes /answer-scripts/:id", async () => {
    mock.onDelete("/answer-scripts/s1").reply(204);
    await expect(removeAnswerScript("s1")).resolves.toBeUndefined();
  });

  it("restoreAnswerScript posts to /answer-scripts/:id/restore", async () => {
    mock.onPost("/answer-scripts/s1/restore").reply(200, { id: "s1" });
    await expect(restoreAnswerScript("s1")).resolves.toEqual({ id: "s1" });
  });

  it("retryAnswerScript posts to /answer-scripts/:id/retry", async () => {
    mock.onPost("/answer-scripts/s1/retry").reply(200, { id: "s1", status: "ocr_queued" });
    await expect(retryAnswerScript("s1")).resolves.toEqual({ id: "s1", status: "ocr_queued" });
  });

  it("cancelAnswerScript posts to /answer-scripts/:id/cancel", async () => {
    mock.onPost("/answer-scripts/s1/cancel").reply(200, { id: "s1", status: "cancelled" });
    await expect(cancelAnswerScript("s1")).resolves.toEqual({ id: "s1", status: "cancelled" });
  });

  it("downloadAnswerScript fetches /answer-scripts/:id/download", async () => {
    mock.onGet("/answer-scripts/s1/download").reply(200, { url: "http://example.test/s1" });
    await expect(downloadAnswerScript("s1")).resolves.toEqual({ url: "http://example.test/s1" });
  });
});

describe("answerScriptPages api module", () => {
  it("listAnswerScriptPages fetches /answer-script-pages", async () => {
    mock.onGet("/answer-script-pages").reply(200, emptyPage);
    await expect(listAnswerScriptPages()).resolves.toEqual(emptyPage);
  });

  it("getAnswerScriptPage fetches /answer-script-pages/:id", async () => {
    mock.onGet("/answer-script-pages/p1").reply(200, { id: "p1" });
    await expect(getAnswerScriptPage("p1")).resolves.toEqual({ id: "p1" });
  });
});

describe("uploadJobs api module", () => {
  it("listUploadJobs fetches /upload-jobs", async () => {
    mock.onGet("/upload-jobs").reply(200, emptyPage);
    await expect(listUploadJobs()).resolves.toEqual(emptyPage);
  });

  it("getUploadJob fetches /upload-jobs/:id", async () => {
    mock.onGet("/upload-jobs/u1").reply(200, { id: "u1" });
    await expect(getUploadJob("u1")).resolves.toEqual({ id: "u1" });
  });
});

describe("ocrProviders api module", () => {
  it("listOCRProviders fetches /ocr-providers", async () => {
    mock.onGet("/ocr-providers").reply(200, emptyPage);
    await expect(listOCRProviders()).resolves.toEqual(emptyPage);
  });

  it("getOCRProvider fetches /ocr-providers/:id", async () => {
    mock.onGet("/ocr-providers/p1").reply(200, { id: "p1" });
    await expect(getOCRProvider("p1")).resolves.toEqual({ id: "p1" });
  });

  it("updateOCRProvider patches /ocr-providers/:id", async () => {
    mock.onPatch("/ocr-providers/p1").reply(200, { id: "p1", is_enabled: true });
    await expect(updateOCRProvider("p1", { is_enabled: true })).resolves.toEqual({
      id: "p1",
      is_enabled: true,
    });
  });
});

describe("ocrConfigurations api module (createCrudApi)", () => {
  it("covers list/get/create/update/remove/restore/listDeleted", async () => {
    mock.onGet("/ocr-configurations").reply(200, emptyPage);
    await expect(ocrConfigurationsApi.list()).resolves.toEqual(emptyPage);

    mock.onGet("/ocr-configurations/deleted").reply(200, emptyPage);
    await expect(ocrConfigurationsApi.listDeleted()).resolves.toEqual(emptyPage);

    mock.onGet("/ocr-configurations/c1").reply(200, { id: "c1" });
    await expect(ocrConfigurationsApi.get("c1")).resolves.toEqual({ id: "c1" });

    mock.onPost("/ocr-configurations").reply(201, { id: "c1" });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- generic payload shape, irrelevant to path coverage
    await expect(ocrConfigurationsApi.create({} as any)).resolves.toEqual({ id: "c1" });

    mock.onPatch("/ocr-configurations/c1").reply(200, { id: "c1" });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- generic payload shape, irrelevant to path coverage
    await expect(ocrConfigurationsApi.update("c1", {} as any)).resolves.toEqual({ id: "c1" });

    mock.onDelete("/ocr-configurations/c1").reply(204);
    await expect(ocrConfigurationsApi.remove("c1")).resolves.toBeUndefined();

    mock.onPost("/ocr-configurations/c1/restore").reply(200, { id: "c1" });
    await expect(ocrConfigurationsApi.restore("c1")).resolves.toEqual({ id: "c1" });
  });
});

describe("ocrJobs api module", () => {
  it("listOCRJobs fetches /ocr-jobs", async () => {
    mock.onGet("/ocr-jobs").reply(200, emptyPage);
    await expect(listOCRJobs()).resolves.toEqual(emptyPage);
  });

  it("getOCRJob fetches /ocr-jobs/:id", async () => {
    mock.onGet("/ocr-jobs/j1").reply(200, { id: "j1" });
    await expect(getOCRJob("j1")).resolves.toEqual({ id: "j1" });
  });

  it("createOCRJob posts to /ocr-jobs", async () => {
    mock.onPost("/ocr-jobs").reply(201, { id: "j1" });
    await expect(
      createOCRJob({ answer_script_id: "s1", ocr_provider_id: "p1" }),
    ).resolves.toEqual({ id: "j1" });
  });

  it("cancelOCRJob posts to /ocr-jobs/:id/cancel", async () => {
    mock.onPost("/ocr-jobs/j1/cancel").reply(200, { id: "j1", status: "cancelled" });
    await expect(cancelOCRJob("j1")).resolves.toEqual({ id: "j1", status: "cancelled" });
  });
});

describe("ocrResults api module", () => {
  it("listOCRResults fetches /ocr-results", async () => {
    mock.onGet("/ocr-results").reply(200, emptyPage);
    await expect(listOCRResults()).resolves.toEqual(emptyPage);
  });

  it("getOCRResult fetches /ocr-results/:id", async () => {
    mock.onGet("/ocr-results/r1").reply(200, { id: "r1" });
    await expect(getOCRResult("r1")).resolves.toEqual({ id: "r1" });
  });

  it("getOCRResultBlocks fetches /ocr-results/:id/blocks", async () => {
    mock.onGet("/ocr-results/r1/blocks").reply(200, []);
    await expect(getOCRResultBlocks("r1")).resolves.toEqual([]);
  });

  it("listOCRBlocks fetches /ocr-blocks", async () => {
    mock.onGet("/ocr-blocks").reply(200, emptyPage);
    await expect(listOCRBlocks()).resolves.toEqual(emptyPage);
  });

  it("listOCRLines fetches /ocr-lines", async () => {
    mock.onGet("/ocr-lines").reply(200, emptyPage);
    await expect(listOCRLines()).resolves.toEqual(emptyPage);
  });

  it("listOCRWords fetches /ocr-words", async () => {
    mock.onGet("/ocr-words").reply(200, emptyPage);
    await expect(listOCRWords()).resolves.toEqual(emptyPage);
  });
});

describe("processingHistory api module", () => {
  it("listProcessingHistory fetches /processing-history", async () => {
    mock.onGet("/processing-history").reply(200, emptyPage);
    await expect(listProcessingHistory()).resolves.toEqual(emptyPage);
  });

  it("getProcessingHistory fetches /processing-history/:id", async () => {
    mock.onGet("/processing-history/h1").reply(200, { id: "h1" });
    await expect(getProcessingHistory("h1")).resolves.toEqual({ id: "h1" });
  });
});
