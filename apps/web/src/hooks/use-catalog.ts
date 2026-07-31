import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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

/**
 * Move one run's soft-delete marker. Nothing stored is removed: a deleted run
 * keeps its summary and Evidence and stays reachable by run_id or through the
 * catalog's "삭제만 보기" filter.
 */
export function useSetRunDeleted() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      runId,
      deleted,
    }: {
      runId: string;
      deleted: boolean;
      /** Set false while marking a batch so the list is re-read only once. */
      refresh?: boolean;
    }) => {
      const request = deleted
        ? apiClient.DELETE("/api/v1/runs/{run_id}", {
            params: { path: { run_id: runId } },
          })
        : apiClient.POST("/api/v1/runs/{run_id}:restore", {
            params: { path: { run_id: runId } },
          });
      const { data, error } = await request;
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("실행 삭제 표시 응답이 비어 있습니다.");
      return data;
    },
    onSuccess: async (result, variables) => {
      if (variables.refresh === false) return;
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["runs"] }),
        queryClient.invalidateQueries({ queryKey: ["run", result.run_id] }),
      ]);
    },
  });
}
