import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { OfficialExamDocumentPage } from "@/types/officialExam";

/**
 * Read-only: `backend/app/api/v1/endpoints/official_exam_document_pages.py`
 * exposes only `GET ""`/`GET "/{id}"` — pages are pipeline-managed, never
 * client-created, mirroring `api/answerScriptPages.ts`.
 */
export async function listOfficialExamDocumentPages(
  params?: PageParams & { document_id?: string },
): Promise<Page<OfficialExamDocumentPage>> {
  const { data } = await apiClient.get<Page<OfficialExamDocumentPage>>(
    "/official-exam-document-pages",
    { params },
  );
  return data;
}

export async function getOfficialExamDocumentPage(id: string): Promise<OfficialExamDocumentPage> {
  const { data } = await apiClient.get<OfficialExamDocumentPage>(
    `/official-exam-document-pages/${id}`,
  );
  return data;
}
