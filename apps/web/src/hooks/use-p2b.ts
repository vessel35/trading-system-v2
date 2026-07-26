import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiClient,
  requestErrorMessage,
  type TagInput,
} from "../api/client";

export function useSweep(sweepId: string | null | undefined) {
  return useQuery({
    queryKey: ["sweep", sweepId],
    enabled: Boolean(sweepId),
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/sweeps/{sweep_id}", {
        params: { path: { sweep_id: sweepId ?? "" } },
      });
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("스윕 결과 응답이 비어 있습니다.");
      return data;
    },
  });
}

export function useCoverage(
  dataSource: string,
  symbol: string,
  exchange: string,
) {
  return useQuery({
    queryKey: ["coverage", dataSource, symbol, exchange],
    enabled: Boolean(dataSource && symbol && exchange),
    queryFn: async () => {
      const { data, error } = await apiClient.GET(
        "/api/v1/data-sources/{data_source}/coverage",
        {
          params: {
            path: { data_source: dataSource },
            query: { symbol, exchange },
          },
        },
      );
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("데이터 커버리지 응답이 비어 있습니다.");
      return data;
    },
  });
}

export function useTagFacets() {
  return useQuery({
    queryKey: ["tag-facets"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/tags/facets");
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("태그 패싯 응답이 비어 있습니다.");
      return data;
    },
  });
}

export function useRunTags(runId: string) {
  return useQuery({
    queryKey: ["run-tags", runId],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/runs/{run_id}/tags", {
        params: { path: { run_id: runId } },
      });
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("실행 태그 응답이 비어 있습니다.");
      return data;
    },
  });
}

export function useAddRunTag(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: TagInput) => {
      const { data, error } = await apiClient.POST("/api/v1/runs/{run_id}/tags", {
        params: { path: { run_id: runId } },
        body,
      });
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("태그 추가 응답이 비어 있습니다.");
      return data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["run-tags", runId] }),
        queryClient.invalidateQueries({ queryKey: ["tag-facets"] }),
      ]);
    },
  });
}

export function useRemoveRunTag(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: TagInput) => {
      const { data, error } = await apiClient.DELETE(
        "/api/v1/runs/{run_id}/tags",
        {
          params: { path: { run_id: runId } },
          body,
        },
      );
      if (error) throw new Error(requestErrorMessage(error));
      if (!data) throw new Error("태그 삭제 응답이 비어 있습니다.");
      return data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["run-tags", runId] }),
        queryClient.invalidateQueries({ queryKey: ["tag-facets"] }),
      ]);
    },
  });
}
