import { createCrudApi } from "@/api/createCrudApi";
import type { ReferenceNote, ReferenceNoteCreate, ReferenceNoteUpdate } from "@/types/assessment";

export const referenceNotesApi = createCrudApi<
  ReferenceNote,
  ReferenceNoteCreate,
  ReferenceNoteUpdate
>("/reference-notes");
