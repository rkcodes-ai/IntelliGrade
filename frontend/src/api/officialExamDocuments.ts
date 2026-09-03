import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type {
  OfficialExamDocument,
  OfficialExamDocumentType,
  OfficialExamDocumentUpdate,
} from "@/types/officialExam";

/**
 * Not a `createCrudApi` object — `POST ""` takes multipart form data (a
 * file + `exam_id` + `document_type`), not a JSON body, mirroring
 * `api/answerScripts.ts` (see `backend/app/api/v1/endpoints/
 * official_exam_documents.py`).
 */
export async function listOfficialExamDocuments(
  params?: PageParams,
): Promise<Page<OfficialExamDocument>> {
  const { data } = await apiClient.get<Page<OfficialExamDocument>>("/official-exam-documents", {
    params,
  });
  return data;
}

export async function listDeletedOfficialExamDocuments(
  params?: PageParams,
): Promise<Page<OfficialExamDocument>> {
  const { data } = await apiClient.get<Page<OfficialExamDocument>>(
    "/official-exam-documents/deleted",
    { params },
  );
  return data;
}

export async function getOfficialExamDocument(id: string): Promise<OfficialExamDocument> {
  const { data } = await apiClient.get<OfficialExamDocument>(`/official-exam-documents/${id}`);
  return data;
}

export async function uploadOfficialExamDocument(
  examId: string,
  documentType: OfficialExamDocumentType,
  file: File,
  options?: { allowDuplicate?: boolean },
): Promise<OfficialExamDocument> {
  const form = new FormData();
  form.append("exam_id", examId);
  form.append("document_type", documentType);
  form.append("file", file);
  if (options?.allowDuplicate) form.append("allow_duplicate", "true");

  const { data } = await apiClient.post<OfficialExamDocument>("/official-exam-documents", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function updateOfficialExamDocument(
  id: string,
  payload: OfficialExamDocumentUpdate,
): Promise<OfficialExamDocument> {
  const { data } = await apiClient.patch<OfficialExamDocument>(
    `/official-exam-documents/${id}`,
    payload,
  );
  return data;
}

export async function removeOfficialExamDocument(id: string): Promise<void> {
  await apiClient.delete(`/official-exam-documents/${id}`);
}

export async function restoreOfficialExamDocument(id: string): Promise<OfficialExamDocument> {
  const { data } = await apiClient.post<OfficialExamDocument>(
    `/official-exam-documents/${id}/restore`,
  );
  return data;
}

export async function retryOfficialExamDocument(id: string): Promise<OfficialExamDocument> {
  const { data } = await apiClient.post<OfficialExamDocument>(
    `/official-exam-documents/${id}/retry`,
  );
  return data;
}

export async function cancelOfficialExamDocument(id: string): Promise<OfficialExamDocument> {
  const { data } = await apiClient.post<OfficialExamDocument>(
    `/official-exam-documents/${id}/cancel`,
  );
  return data;
}

export async function downloadOfficialExamDocument(id: string): Promise<{ url: string }> {
  const { data } = await apiClient.get<{ url: string }>(`/official-exam-documents/${id}/download`);
  return data;
}
