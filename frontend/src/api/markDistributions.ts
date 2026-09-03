import { createCrudApi } from "@/api/createCrudApi";
import type {
  MarkDistribution,
  MarkDistributionCreate,
  MarkDistributionUpdate,
} from "@/types/assessment";

export const markDistributionsApi = createCrudApi<
  MarkDistribution,
  MarkDistributionCreate,
  MarkDistributionUpdate
>("/mark-distributions");
