import {
  useEffect,
  useState,
} from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  apiClient,
  apiRequestError,
  type DataJobRequest,
  type DataJobStatus,
} from "../api/client";

const dataJobsQueryKey = ["data-jobs"] as const;
const terminalStatuses = new Set<DataJobStatus["status"]>([
  "SUCCEEDED",
  "FAILED",
]);

function eventUrl(jobId: string): string {
  const path = `/api/v1/data-jobs/${encodeURIComponent(jobId)}/events`;
  const base = import.meta.env.VITE_API_BASE_URL;
  if (!base) return path;
  return new URL(path, base).toString();
}

function replaceJob(
  jobs: DataJobStatus[] | undefined,
  next: DataJobStatus,
): DataJobStatus[] {
  return [
    next,
    ...(jobs ?? []).filter((job) => job.job_id !== next.job_id),
  ];
}

export function useDataJobs() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: dataJobsQueryKey,
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/data-jobs");
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("데이터 작업 목록 응답이 비어 있습니다.");
      return data;
    },
  });
  const trigger = useMutation({
    mutationFn: async (body: DataJobRequest) => {
      const { data, error } = await apiClient.POST("/api/v1/data-jobs", {
        body,
      });
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("데이터 작업 생성 응답이 비어 있습니다.");
      return data;
    },
    onSuccess: (job) => {
      queryClient.setQueryData<DataJobStatus[]>(dataJobsQueryKey, (current) =>
        replaceJob(current, job),
      );
      queryClient.setQueryData(["data-job", job.job_id], job);
    },
  });

  return {
    ...query,
    trigger: trigger.mutateAsync,
    triggerState: trigger,
  };
}

export function useDataJob(
  jobId: string,
  initialData?: DataJobStatus,
) {
  const queryClient = useQueryClient();
  const [sseUnavailable, setSseUnavailable] = useState(
    () => typeof EventSource === "undefined",
  );
  const query = useQuery({
    queryKey: ["data-job", jobId],
    enabled: Boolean(jobId),
    initialData,
    staleTime: 1_000,
    queryFn: async () => {
      const { data, error } = await apiClient.GET(
        "/api/v1/data-jobs/{job_id}",
        {
          params: { path: { job_id: jobId } },
        },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("데이터 작업 상태 응답이 비어 있습니다.");
      return data;
    },
    refetchInterval: (current) => {
      const status = current.state.data?.status;
      if (!sseUnavailable || !status || terminalStatuses.has(status)) return false;
      return 1_500;
    },
  });

  useEffect(() => {
    if (!jobId || typeof EventSource === "undefined") return;
    if (query.data && terminalStatuses.has(query.data.status)) return;

    setSseUnavailable(false);
    const source = new EventSource(eventUrl(jobId));
    const update = (next: DataJobStatus) => {
      queryClient.setQueryData(["data-job", jobId], next);
      queryClient.setQueryData<DataJobStatus[]>(dataJobsQueryKey, (current) =>
        replaceJob(current, next),
      );
      if (terminalStatuses.has(next.status)) source.close();
    };

    source.addEventListener("status", (event) => {
      try {
        update(JSON.parse((event as MessageEvent<string>).data) as DataJobStatus);
      } catch {
        setSseUnavailable(true);
        source.close();
        void query.refetch();
      }
    });
    source.onerror = () => {
      setSseUnavailable(true);
      source.close();
      void query.refetch();
    };

    return () => source.close();
  }, [jobId, query.refetch, queryClient]);

  return query;
}
