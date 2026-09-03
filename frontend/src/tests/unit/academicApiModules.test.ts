import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { academicYearsApi } from "@/api/academicYears";
import { listAcademicStatuses } from "@/api/academicStatuses";
import { listBatches } from "@/api/batches";
import { campusesApi } from "@/api/campuses";
import { apiClient } from "@/api/client";
import { coursesApi } from "@/api/courses";
import { createCrudApi } from "@/api/createCrudApi";
import { departmentsApi } from "@/api/departments";
import {
  assignInstitutionMember,
  institutionsApi,
  listInstitutionMembers,
  listMyInstitutions,
  revokeInstitutionMember,
} from "@/api/institutions";
import { programsApi } from "@/api/programs";
import { sectionsApi } from "@/api/sections";
import { semestersApi } from "@/api/semesters";
import { listSubjectAllocations } from "@/api/subjectAllocations";
import { listSubjectCategories } from "@/api/subjectCategories";
import { studentEnrollmentsApi } from "@/api/studentEnrollments";
import { subjectsApi } from "@/api/subjects";
import { teacherAssignmentsApi } from "@/api/teacherAssignments";

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(apiClient);
});

afterEach(() => {
  mock.restore();
});

const emptyPage = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };

describe("createCrudApi", () => {
  interface Widget {
    id: string;
    name: string;
  }

  const widgetsApi = createCrudApi<Widget, { name: string }, { name?: string }>("/widgets");

  it("list fetches the base path with params", async () => {
    mock.onGet("/widgets").reply((config) => {
      expect(config.params).toEqual({ page: 1 });
      return [200, { ...emptyPage, items: [{ id: "w1", name: "Widget" }] }];
    });
    const result = await widgetsApi.list({ page: 1 });
    expect(result.items).toHaveLength(1);
  });

  it("listDeleted fetches /widgets/deleted", async () => {
    mock.onGet("/widgets/deleted").reply(200, emptyPage);
    const result = await widgetsApi.listDeleted();
    expect(result.total).toBe(0);
  });

  it("get fetches /widgets/:id", async () => {
    mock.onGet("/widgets/w1").reply(200, { id: "w1", name: "Widget" });
    const result = await widgetsApi.get("w1");
    expect(result.name).toBe("Widget");
  });

  it("create posts to /widgets", async () => {
    mock.onPost("/widgets").reply(201, { id: "w1", name: "New" });
    const result = await widgetsApi.create({ name: "New" });
    expect(result.id).toBe("w1");
  });

  it("update patches /widgets/:id", async () => {
    mock.onPatch("/widgets/w1").reply(200, { id: "w1", name: "Updated" });
    const result = await widgetsApi.update("w1", { name: "Updated" });
    expect(result.name).toBe("Updated");
  });

  it("remove deletes /widgets/:id", async () => {
    mock.onDelete("/widgets/w1").reply(204);
    await expect(widgetsApi.remove("w1")).resolves.toBeUndefined();
  });

  it("restore posts to /widgets/:id/restore", async () => {
    mock.onPost("/widgets/w1/restore").reply(200, { id: "w1", name: "Widget" });
    const result = await widgetsApi.restore("w1");
    expect(result.id).toBe("w1");
  });
});

describe("entity api modules resolve to the correct backend paths", () => {
  it.each([
    ["campuses", campusesApi, "/campuses"],
    ["departments", departmentsApi, "/departments"],
    ["programs", programsApi, "/programs"],
    ["courses", coursesApi, "/courses"],
    ["academicYears", academicYearsApi, "/academic-years"],
    ["semesters", semestersApi, "/semesters"],
    ["sections", sectionsApi, "/sections"],
    ["subjects", subjectsApi, "/subjects"],
    ["teacherAssignments", teacherAssignmentsApi, "/teacher-assignments"],
    ["studentEnrollments", studentEnrollmentsApi, "/student-enrollments"],
    ["institutions", institutionsApi, "/institutions"],
  ] as const)("%s.list hits %s", async (_name, api, path) => {
    mock.onGet(path).reply(200, emptyPage);
    const result = await api.list();
    expect(result).toEqual(emptyPage);
  });
});

describe("institutions api extras", () => {
  it("listMyInstitutions fetches /institutions/mine", async () => {
    mock.onGet("/institutions/mine").reply(200, [{ id: "inst-1", name: "Acme" }]);
    const result = await listMyInstitutions();
    expect(result).toHaveLength(1);
  });

  it("listInstitutionMembers fetches /institutions/:id/members", async () => {
    mock.onGet("/institutions/inst-1/members").reply(200, []);
    const result = await listInstitutionMembers("inst-1");
    expect(result).toEqual([]);
  });

  it("assignInstitutionMember posts a member", async () => {
    mock.onPost("/institutions/inst-1/members").reply(201, { id: "m1" });
    const result = await assignInstitutionMember("inst-1", { user_id: "u1" });
    expect(result.id).toBe("m1");
  });

  it("revokeInstitutionMember deletes a member", async () => {
    mock.onDelete("/institutions/inst-1/members/u1").reply(204);
    await expect(revokeInstitutionMember("inst-1", "u1")).resolves.toBeUndefined();
  });
});

describe("read-only supporting entity api modules", () => {
  it("listBatches fetches /batches", async () => {
    mock.onGet("/batches").reply(200, emptyPage);
    await expect(listBatches()).resolves.toEqual(emptyPage);
  });

  it("listSubjectCategories fetches /subject-categories", async () => {
    mock.onGet("/subject-categories").reply(200, emptyPage);
    await expect(listSubjectCategories()).resolves.toEqual(emptyPage);
  });

  it("listSubjectAllocations fetches /subject-allocations", async () => {
    mock.onGet("/subject-allocations").reply(200, emptyPage);
    await expect(listSubjectAllocations()).resolves.toEqual(emptyPage);
  });

  it("listAcademicStatuses fetches /academic-statuses", async () => {
    mock.onGet("/academic-statuses").reply(200, emptyPage);
    await expect(listAcademicStatuses()).resolves.toEqual(emptyPage);
  });
});
