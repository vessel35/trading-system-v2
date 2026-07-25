import { useQuery } from "@tanstack/react-query";

import {
  apiClient,
  requestErrorMessage,
  type RunQuery,
} from "../api/client";

export function useRuns(query: RunQuery) {
  return useQuery({
    queryKey: ["runs", query],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/runs", {
        params: { query },
      });
      if (error) {
        throw new Error(requestErrorMessage(error));
      }
      if (!data) {
        throw new Error("카탈로그 응답이 비어 있습니다.");
      }
      return data;
    },
    placeholderData: (previous) => previous,
  });
}

export function useRun(runId: string) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/runs/{run_id}", {
        params: { path: { run_id: runId } },
      });
      if (error) {
        throw new Error(requestErrorMessage(error));
      }
      if (!data) {
        throw new Error("실행 헤더 응답이 비어 있습니다.");
      }
      return data;
    },
  });
}

export function useRunSummary(runId: string) {
  return useQuery({
    queryKey: ["run-summary", runId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/summary",
        {
          params: { path: { run_id: runId } },
        },
      );
      if (error) {
        throw new Error(requestErrorMessage(error));
      }
      if (!data) {
        throw new Error("실행 요약 응답이 비어 있습니다.");
      }
      return data;
    },
  });
}
