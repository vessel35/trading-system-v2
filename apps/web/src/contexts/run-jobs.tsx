import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  apiClient,
  type JobStatus,
  type RunAccepted,
  type RunSubmission,
  type SweepSubmission,
} from "../api/client";

export interface TrackedJob {
  accepted: RunAccepted;
  status: JobStatus;
  submission: RunSubmission;
  submittedAt: string;
}

export interface TrackedSweep {
  accepted: RunAccepted;
  status: JobStatus;
  submission: SweepSubmission;
  submittedAt: string;
}

interface RunJobsValue {
  jobs: TrackedJob[];
  sweeps: TrackedSweep[];
  track: (accepted: RunAccepted, submission: RunSubmission) => void;
  trackSweep: (accepted: RunAccepted, submission: SweepSubmission) => void;
}

const RunJobsContext = createContext<RunJobsValue | null>(null);
const terminalStatuses = new Set<JobStatus["status"]>([
  "SUCCEEDED",
  "FAILED",
  "ORPHANED",
]);

function eventUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL;
  if (!base) return path;
  return new URL(path, base).toString();
}

export function RunJobsProvider({ children }: PropsWithChildren) {
  const [jobs, setJobs] = useState<TrackedJob[]>([]);
  const [sweeps, setSweeps] = useState<TrackedSweep[]>([]);
  const sources = useRef(new Map<string, EventSource>());
  const reconnectTimers = useRef(new Map<string, number>());

  const updateStatus = useCallback((jobId: string, status: JobStatus) => {
    setJobs((current) =>
      current.map((job) =>
        job.accepted.job_id === jobId ? { ...job, status } : job,
      ),
    );
    setSweeps((current) =>
      current.map((sweep) =>
        sweep.accepted.job_id === jobId ? { ...sweep, status } : sweep,
      ),
    );
  }, []);

  const subscribe = useCallback(
    (accepted: RunAccepted) => {
      const existing = sources.current.get(accepted.job_id);
      existing?.close();

      const source = new EventSource(eventUrl(accepted.events_url));
      sources.current.set(accepted.job_id, source);
      source.addEventListener("status", (event) => {
        const status = JSON.parse((event as MessageEvent<string>).data) as JobStatus;
        updateStatus(accepted.job_id, status);
        if (terminalStatuses.has(status.status)) {
          source.close();
          sources.current.delete(accepted.job_id);
        }
      });
      source.onerror = () => {
        source.close();
        sources.current.delete(accepted.job_id);
        void apiClient
          .GET("/api/v1/jobs/{job_id}/status", {
            params: { path: { job_id: accepted.job_id } },
          })
          .then(({ data }) => {
            if (!data) return;
            updateStatus(accepted.job_id, data);
            if (!terminalStatuses.has(data.status)) {
              const timer = window.setTimeout(() => subscribe(accepted), 1_500);
              reconnectTimers.current.set(accepted.job_id, timer);
            }
          });
      };
    },
    [updateStatus],
  );

  const track = useCallback(
    (accepted: RunAccepted, submission: RunSubmission) => {
      const now = new Date().toISOString();
      const status: JobStatus = {
        job_id: accepted.job_id,
        status: accepted.status,
        updated_at: now,
      };
      setJobs((current) => [
        {
          accepted,
          status,
          submission,
          submittedAt: now,
        },
        ...current.filter((job) => job.accepted.job_id !== accepted.job_id),
      ]);
      subscribe(accepted);
    },
    [subscribe],
  );

  const trackSweep = useCallback(
    (accepted: RunAccepted, submission: SweepSubmission) => {
      const now = new Date().toISOString();
      const status: JobStatus = {
        job_id: accepted.job_id,
        status: accepted.status,
        updated_at: now,
      };
      setSweeps((current) => [
        {
          accepted,
          status,
          submission,
          submittedAt: now,
        },
        ...current.filter((sweep) => sweep.accepted.job_id !== accepted.job_id),
      ]);
      subscribe(accepted);
    },
    [subscribe],
  );

  useEffect(
    () => () => {
      sources.current.forEach((source) => source.close());
      reconnectTimers.current.forEach((timer) => window.clearTimeout(timer));
    },
    [],
  );

  const value = useMemo(
    () => ({ jobs, sweeps, track, trackSweep }),
    [jobs, sweeps, track, trackSweep],
  );
  return <RunJobsContext.Provider value={value}>{children}</RunJobsContext.Provider>;
}

export function useRunJobs(): RunJobsValue {
  const value = useContext(RunJobsContext);
  if (!value) {
    throw new Error("useRunJobs must be used within RunJobsProvider");
  }
  return value;
}
