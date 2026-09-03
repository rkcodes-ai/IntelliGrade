import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { OCRTextViewerPage } from "@/pages/ocr/OCRTextViewerPage";
import type { OCRBlockWithChildren, OCRResult } from "@/types/ocr";

const { navigateMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
}));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

const { getOCRResultMock, getOCRResultBlocksMock } = vi.hoisted(() => ({
  getOCRResultMock: vi.fn(),
  getOCRResultBlocksMock: vi.fn(),
}));
vi.mock("@/api/ocrResults", () => ({
  getOCRResult: getOCRResultMock,
  getOCRResultBlocks: getOCRResultBlocksMock,
  listOCRResults: vi.fn(),
  listOCRBlocks: vi.fn(),
  listOCRLines: vi.fn(),
  listOCRWords: vi.fn(),
}));

const ocrResult: OCRResult = {
  id: "result-1",
  institution_id: "inst-1",
  answer_script_page_id: "page-1",
  ocr_job_id: "job-1",
  raw_text: "Raw sample text",
  normalized_text: "Normalized sample text",
  average_confidence: "0.9500",
  language: "eng",
  rotation_degrees: "0.00",
  reading_order_verified: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const blocks: OCRBlockWithChildren[] = [
  {
    id: "block-1",
    institution_id: "inst-1",
    ocr_result_id: "result-1",
    block_type: "paragraph",
    reading_order: 0,
    bbox_left: 0,
    bbox_top: 0,
    bbox_width: 100,
    bbox_height: 20,
    confidence: "0.9000",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    lines: [
      {
        id: "line-1",
        institution_id: "inst-1",
        ocr_block_id: "block-1",
        text: "Line one text",
        reading_order: 0,
        bbox_left: 0,
        bbox_top: 0,
        bbox_width: 100,
        bbox_height: 10,
        confidence: "0.8800",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        words: [
          {
            id: "word-1",
            institution_id: "inst-1",
            ocr_line_id: "line-1",
            text: "Hello",
            reading_order: 0,
            bbox_left: 0,
            bbox_top: 0,
            bbox_width: 30,
            bbox_height: 10,
            confidence: "0.9900",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
    ],
  },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/dashboard/ocr-results/result-1"]}>
        <Routes>
          <Route path="/dashboard/ocr-results/:id" element={<OCRTextViewerPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OCRTextViewerPage", () => {
  it("renders raw and normalized text", async () => {
    getOCRResultMock.mockResolvedValueOnce(ocrResult);
    getOCRResultBlocksMock.mockResolvedValueOnce([]);
    renderPage();

    expect(await screen.findByText("Raw sample text")).toBeInTheDocument();
    expect(screen.getByText("Normalized sample text")).toBeInTheDocument();
    expect(screen.getByText("0.9500")).toBeInTheDocument();
    expect(screen.getByText("eng")).toBeInTheDocument();
  });

  it("shows a fallback when normalized text is not yet available", async () => {
    getOCRResultMock.mockResolvedValueOnce({ ...ocrResult, normalized_text: null });
    getOCRResultBlocksMock.mockResolvedValueOnce([]);
    renderPage();

    expect(await screen.findByText("Not yet normalized")).toBeInTheDocument();
  });

  it("renders the block/line/word tree with correct nesting", async () => {
    getOCRResultMock.mockResolvedValueOnce(ocrResult);
    getOCRResultBlocksMock.mockResolvedValueOnce(blocks);
    renderPage();

    const blockSummary = await screen.findByText("paragraph · confidence 0.9000");
    const blockDetails = blockSummary.closest("details");
    expect(blockDetails).not.toBeNull();

    const lineText = within(blockDetails as HTMLElement).getByText(
      "Line one text · confidence 0.8800",
    );
    const lineDetails = lineText.closest("details");
    expect(lineDetails).not.toBeNull();
    expect(blockDetails).not.toBe(lineDetails);

    expect(within(lineDetails as HTMLElement).getByText(/Hello/)).toBeInTheDocument();
  });

  it("navigates back when Back is clicked", async () => {
    getOCRResultMock.mockResolvedValueOnce(ocrResult);
    getOCRResultBlocksMock.mockResolvedValueOnce([]);
    renderPage();

    await screen.findByText("Raw sample text");
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(navigateMock).toHaveBeenCalledWith(-1);
  });
});
