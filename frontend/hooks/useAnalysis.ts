"use client";

import { useQuery } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { AnalysisReport } from "@/types";

export function useAnalysis(sessionId: string) {
  return useQuery<AnalysisReport>({
    queryKey: ["analysis", sessionId],
    queryFn: async () => {
      const { data, error } = await client.GET("/sessions/{id}/analysis", {
        params: { path: { id: sessionId } },
      });
      if (error) throw new Error(String(error));
      return data!;
    },
    enabled: !!sessionId,
    staleTime: 30_000,
  });
}
