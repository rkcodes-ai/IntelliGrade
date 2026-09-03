import { createCrudApi } from "@/api/createCrudApi";
import type { Department, DepartmentCreate, DepartmentUpdate } from "@/types/academic";

export const departmentsApi = createCrudApi<Department, DepartmentCreate, DepartmentUpdate>(
  "/departments",
);
