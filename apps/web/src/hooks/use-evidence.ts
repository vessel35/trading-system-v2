import { useQuery } from "@tanstack/react-query";

import {
  apiClient,
  apiRequestError,
  type CandidateEvent,
  type CandleCollection,
  type ChartSummary,
  type ConditionalExpectancy,
  type Decision,
  type DrawdownEpisode,
  type EquityPoint,
  type Execution,
  type FundingSettlement,
  type IntegrityCheck,
  type IndicatorSnapshot,
  type Finding,
  type MissedOpportunity,
  type OutcomeBucket,
  type Position,
  type PreregistrationResponse,
  type Signal,
  type Trade,
  type TradeFeature,
} from "../api/client";

type CursorResponse<T> = {
  data: T[];
  page: {
    has_more: boolean;
    next_after_seq: number | null;
  };
};

export async function allPages<T>(
  request: (afterSeq: number) => Promise<CursorResponse<T>>,
): Promise<T[]> {
  const rows: T[] = [];
  let afterSeq = 0;
  for (;;) {
    const page = await request(afterSeq);
    rows.push(...page.data);
    if (!page.page.has_more || page.page.next_after_seq === null) {
      return rows;
    }
    afterSeq = page.page.next_after_seq;
  }
}

function cursorQuery<T>(
  queryKey: readonly unknown[],
  request: (afterSeq: number) => Promise<CursorResponse<T>>,
) {
  return useQuery({
    queryKey,
    queryFn: () => allPages(request),
  });
}

export function useTrades(runId: string) {
  return useQuery({
    queryKey: ["evidence", runId, "trades"],
    queryFn: () =>
      allPages<Trade>(async (after_seq) => {
        const { data, error } = await apiClient.GET(
          "/api/v1/runs/{run_id}/trades",
          {
            params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
          },
        );
        if (error) throw apiRequestError(error);
        if (!data) throw new Error("거래 Evidence 응답이 비어 있습니다.");
        return data;
      }),
  });
}

export function useEquityEvidence(runId: string) {
  const chart = useQuery({
    queryKey: ["evidence", runId, "chart-summaries"],
    queryFn: () =>
      allPages<ChartSummary>(async (after_seq) => {
        const { data, error } = await apiClient.GET(
          "/api/v1/runs/{run_id}/chart-summaries",
          {
            params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
          },
        );
        if (error) throw apiRequestError(error);
        if (!data) throw new Error("차트 Evidence 응답이 비어 있습니다.");
        return data;
      }),
  });
  const chartHasEquity =
    chart.data?.some((point) => point.series_name === "equity") ?? false;
  const equity = useQuery({
    queryKey: ["evidence", runId, "equity"],
    queryFn: () =>
      allPages<EquityPoint>(async (after_seq) => {
        const { data, error } = await apiClient.GET(
          "/api/v1/runs/{run_id}/equity",
          {
            params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
          },
        );
        if (error) throw apiRequestError(error);
        if (!data) throw new Error("자본 Evidence 응답이 비어 있습니다.");
        return data;
      }),
    enabled: chart.isSuccess && !chartHasEquity,
  });
  return { chart, equity };
}

export function useExecutions(runId: string, tradeId?: number) {
  return useQuery({
    queryKey: ["evidence", runId, "executions", tradeId ?? "all"],
    queryFn: () =>
      allPages<Execution>(async (after_seq) => {
        const { data, error } = await apiClient.GET(
          "/api/v1/runs/{run_id}/executions",
          {
            params: {
              path: { run_id: runId },
              query: { after_seq, limit: 200, trade_id: tradeId },
            },
          },
        );
        if (error) throw apiRequestError(error);
        if (!data) throw new Error("체결 Evidence 응답이 비어 있습니다.");
        return data;
      }),
    enabled: tradeId === undefined || tradeId > 0,
  });
}

export function useDrawdownEpisodes(runId: string) {
  return useQuery({
    queryKey: ["evidence", runId, "drawdown-episodes"],
    queryFn: () =>
      allPages<DrawdownEpisode>(async (after_seq) => {
        const { data, error } = await apiClient.GET(
          "/api/v1/runs/{run_id}/drawdown-episodes",
          {
            params: {
              path: { run_id: runId },
              query: { after_seq, limit: 200, kind: "drawdown" },
            },
          },
        );
        if (error) throw apiRequestError(error);
        if (!data) throw new Error("드로다운 Evidence 응답이 비어 있습니다.");
        return data;
      }),
  });
}

export function useOutcomeBuckets(runId: string) {
  return useQuery({
    queryKey: ["evidence", runId, "outcome-buckets"],
    queryFn: () =>
      allPages<OutcomeBucket>(async (after_seq) => {
        const { data, error } = await apiClient.GET(
          "/api/v1/runs/{run_id}/outcome-buckets",
          {
            params: {
              path: { run_id: runId },
              query: {
                after_seq,
                limit: 200,
                subject_kind: "trade",
                bucket_name: "outcome_class",
              },
            },
          },
        );
        if (error) throw apiRequestError(error);
        if (!data) throw new Error("결과 버킷 응답이 비어 있습니다.");
        return data;
      }),
  });
}

export function useIntegrityChecks(runId: string) {
  return useQuery({
    queryKey: ["evidence", runId, "integrity-checks"],
    queryFn: () =>
      allPages<IntegrityCheck>(async (after_seq) => {
        const { data, error } = await apiClient.GET(
          "/api/v1/runs/{run_id}/integrity-checks",
          {
            params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
          },
        );
        if (error) throw apiRequestError(error);
        if (!data) throw new Error("무결성 Evidence 응답이 비어 있습니다.");
        return data;
      }),
  });
}

export function useTradeDrawerEvidence(runId: string, tradeId: number | null) {
  const enabled = tradeId !== null;
  const funding = useQuery({
    queryKey: ["evidence", runId, "funding", tradeId],
    queryFn: () =>
      allPages<FundingSettlement>(async (after_seq) => {
        const { data, error } = await apiClient.GET(
          "/api/v1/runs/{run_id}/funding-settlements",
          {
            params: {
              path: { run_id: runId },
              query: { after_seq, limit: 200, trade_id: tradeId ?? undefined },
            },
          },
        );
        if (error) throw apiRequestError(error);
        if (!data) throw new Error("펀딩 Evidence 응답이 비어 있습니다.");
        return data;
      }),
    enabled,
  });
  const features = useQuery({
    queryKey: ["evidence", runId, "trade-features", tradeId],
    queryFn: () =>
      allPages<TradeFeature>(async (after_seq) => {
        const { data, error } = await apiClient.GET(
          "/api/v1/runs/{run_id}/trade-features",
          {
            params: {
              path: { run_id: runId },
              query: { after_seq, limit: 200, trade_id: tradeId ?? undefined },
            },
          },
        );
        if (error) throw apiRequestError(error);
        if (!data) throw new Error("거래 특징 응답이 비어 있습니다.");
        return data;
      }),
    enabled,
  });
  const candidates = useQuery({
    queryKey: ["evidence", runId, "candidate-events", tradeId],
    queryFn: () =>
      allPages<CandidateEvent>(async (after_seq) => {
        const { data, error } = await apiClient.GET(
          "/api/v1/runs/{run_id}/candidate-events",
          {
            params: {
              path: { run_id: runId },
              query: {
                after_seq,
                limit: 200,
                linked_trade_id: tradeId ?? undefined,
              },
            },
          },
        );
        if (error) throw apiRequestError(error);
        if (!data) throw new Error("후보 Evidence 응답이 비어 있습니다.");
        return data;
      }),
    enabled,
  });
  const positions = useQuery({
    queryKey: ["evidence", runId, "positions", tradeId],
    queryFn: () =>
      allPages<Position>(async (after_seq) => {
        const { data, error } = await apiClient.GET(
          "/api/v1/runs/{run_id}/positions",
          {
            params: {
              path: { run_id: runId },
              query: { after_seq, limit: 200, trade_id: tradeId ?? undefined },
            },
          },
        );
        if (error) throw apiRequestError(error);
        if (!data) throw new Error("포지션 Evidence 응답이 비어 있습니다.");
        return data;
      }),
    enabled,
  });
  return { funding, features, candidates, positions };
}

export function useChartEvidence(runId: string) {
  const candles = useQuery({
    queryKey: ["evidence", runId, "candles"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/candles",
        {
          params: { path: { run_id: runId }, query: { limit: 5000 } },
        },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("캔들 응답이 비어 있습니다.");
      return data as CandleCollection;
    },
  });
  const indicators = cursorQuery<IndicatorSnapshot>(
    ["evidence", runId, "indicator-snapshots"],
    async (after_seq) => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/indicator-snapshots",
        {
          params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
        },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("지표 스냅샷 응답이 비어 있습니다.");
      return data;
    },
  );
  const signals = useSignals(runId);
  const candidates = useCandidateEvents(runId);
  const executions = useExecutions(runId);
  return { candles, indicators, signals, candidates, executions };
}

export function useSignals(runId: string) {
  return cursorQuery<Signal>(["evidence", runId, "signals"], async (after_seq) => {
    const { data, error } = await apiClient.GET("/api/v1/runs/{run_id}/signals", {
      params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
    });
    if (error) throw apiRequestError(error);
    if (!data) throw new Error("신호 Evidence 응답이 비어 있습니다.");
    return data;
  });
}

export function useDecisions(runId: string) {
  return cursorQuery<Decision>(
    ["evidence", runId, "decisions"],
    async (after_seq) => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/decisions",
        {
          params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
        },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("의사결정 Evidence 응답이 비어 있습니다.");
      return data;
    },
  );
}

export function useCandidateEvents(runId: string) {
  return cursorQuery<CandidateEvent>(
    ["evidence", runId, "candidate-events", "all"],
    async (after_seq) => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/candidate-events",
        {
          params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
        },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("후보 Evidence 응답이 비어 있습니다.");
      return data;
    },
  );
}

export function useMissedOpportunities(runId: string) {
  return cursorQuery<MissedOpportunity>(
    ["evidence", runId, "missed-opportunities"],
    async (after_seq) => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/missed-opportunities",
        {
          params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
        },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("놓친 기회 Evidence 응답이 비어 있습니다.");
      return data;
    },
  );
}

export function useResearchEvidence(runId: string) {
  const conditional = cursorQuery<ConditionalExpectancy>(
    ["evidence", runId, "conditional-expectancy"],
    async (after_seq) => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/conditional-expectancy",
        {
          params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
        },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("조건부 기대값 응답이 비어 있습니다.");
      return data;
    },
  );
  const findings = cursorQuery<Finding>(
    ["evidence", runId, "findings"],
    async (after_seq) => {
      const { data, error } = await apiClient.GET("/api/v1/runs/{run_id}/findings", {
        params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
      });
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("연구 노트 응답이 비어 있습니다.");
      return data;
    },
  );
  const prereg = useQuery({
    queryKey: ["catalog", runId, "prereg"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/runs/{run_id}/prereg", {
        params: { path: { run_id: runId } },
      });
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("사전등록 응답이 비어 있습니다.");
      return data as PreregistrationResponse;
    },
  });
  return { conditional, findings, prereg };
}
