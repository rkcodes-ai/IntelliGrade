import { createCrudApi } from "@/api/createCrudApi";
import type { Course, CourseCreate, CourseUpdate } from "@/types/academic";

export const coursesApi = createCrudApi<Course, CourseCreate, CourseUpdate>("/courses");
