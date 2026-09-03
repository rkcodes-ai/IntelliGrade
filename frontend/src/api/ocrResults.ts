import { apiClient } from "@/api/client";
import type { Page, PageParams } from "@/types/pagination";
import type { OCRBlock, OCRBlockWithChildren, OCRLine, OCRResult, OCRWord } from "@/types/ocr";

/**
 * Read-only for all four entities in this hierarchy
 * (`OCRResult`/`OCRBlock`/`OCRLine`/`OCRWord`) — see
 * `backend/app/api/v1/endpoints/ocr_results.py`. None of the five `GET ""`
 * routes support server-side filtering by parent id — `getOCRResultBlocks`
 * hits the nested tree route instead, which is what the OCR Text Viewer /
 * bounding-box overlay actually needs (a page's full block->line->word
 * tree in one call).
 */
export async function listOCRResults(params?: PageParams): Promise<Page<OCRResult>> {
  const { data } = await apiClient.get<Page<OCRResult>>("/ocr-results", { params });
  return data;
}

export async function getOCRResult(id: string): Promise<OCRResult> {
  const { data } = await apiClient.get<OCRResult>(`/ocr-results/${id}`);
  return data;
}

export async function getOCRResultBlocks(id: string): Promise<OCRBlockWithChildren[]> {
  const { data } = await apiClient.get<OCRBlockWithChildren[]>(`/ocr-results/${id}/blocks`);
  return data;
}

export async function listOCRBlocks(params?: PageParams): Promise<Page<OCRBlock>> {
  const { data } = await apiClient.get<Page<OCRBlock>>("/ocr-blocks", { params });
  return data;
}

export async function listOCRLines(params?: PageParams): Promise<Page<OCRLine>> {
  const { data } = await apiClient.get<Page<OCRLine>>("/ocr-lines", { params });
  return data;
}

export async function listOCRWords(params?: PageParams): Promise<Page<OCRWord>> {
  const { data } = await apiClient.get<Page<OCRWord>>("/ocr-words", { params });
  return data;
}
