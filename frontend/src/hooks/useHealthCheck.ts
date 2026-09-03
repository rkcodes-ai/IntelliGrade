import { useQuery } from "@tanstack/react-query";

import { fetchHealthStatus } from "@/api/health";

export function useHealthCheck() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealthStatus,
    staleTime: 10_000,
  });
}
