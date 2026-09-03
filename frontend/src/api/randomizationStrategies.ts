import { createCrudApi } from "@/api/createCrudApi";
import type {
  RandomizationStrategy,
  RandomizationStrategyCreate,
  RandomizationStrategyUpdate,
} from "@/types/assessment";

export const randomizationStrategiesApi = createCrudApi<
  RandomizationStrategy,
  RandomizationStrategyCreate,
  RandomizationStrategyUpdate
>("/randomization-strategies");
