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
  type IndicatorDefinition,
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

export const EVIDENCE_ROW_LIMIT = 5_000;
export const EVIDENCE_PAGE_LIMIT = 25;

export interface EvidencePage<T> {
  readonly rows: T[];
  readonly truncated: boolean;
  readonly limit: number;
  readonly pageLimit: number;
}

export interface IndicatorEvidencePage extends EvidencePage<IndicatorSnapshot> {
  readonly truncatedKeys: string[];
}

function evidencePage<T>(rows: T[], truncated: boolean): EvidencePage<T> {
  return {
    rows,
    truncated,
    limit: EVIDENCE_ROW_LIMIT,
    pageLimit: EVIDENCE_PAGE_LIMIT,
  };
}

export function isTruncatedEvidence(
  value: EvidencePage<unknown> | null | undefined,
): boolean {
  return value?.truncated ?? false;
}

export async function allPages<T>(
  request: (afterSeq: number) => Promise<CursorResponse<T>>,
): Promise<EvidencePage<T>> {
  const rows: T[] = [];
  let afterSeq = 0;
  for (let pageCount = 1; pageCount <= EVIDENCE_PAGE_LIMIT; pageCount += 1) {
    const page = await request(afterSeq);
    const remaining = EVIDENCE_ROW_LIMIT - rows.length;
    rows.push(...page.data.slice(0, remaining));
    if (!page.page.has_more || page.page.next_after_seq === null) {
      return evidencePage(rows, page.data.length > remaining);
    }
    if (
      rows.length >= EVIDENCE_ROW_LIMIT ||
      pageCount >= EVIDENCE_PAGE_LIMIT ||
      page.page.next_after_seq === afterSeq
    ) {
      return evidencePage(rows, true);
    }
    afterSeq = page.page.next_after_seq;
  }
  return evidencePage(rows, true);
}

function useCursorQuery<T>(
  queryKey: readonly unknown[],
  request: (afterSeq: number) => Promise<CursorResponse<T>>,
  enabled = true,
) {
  const query = useQuery({
    queryKey,
    queryFn: () => allPages(request),
    enabled,
  });
  return {
    ...query,
    data: query.data?.rows,
    evidence: query.data,
  };
}

export function useTrades(runId: string) {
  return useCursorQuery<Trade>(
    ["evidence", runId, "trades"],
    async (after_seq) => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/trades",
        {
          params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
        },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("거래 Evidence 응답이 비어 있습니다.");
      return data;
    },
  );
}

export function useEquityEvidence(runId: string) {
  const chart = useCursorQuery<ChartSummary>(
    ["evidence", runId, "chart-summaries"],
    async (after_seq) => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/chart-summaries",
        {
          params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
        },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("차트 Evidence 응답이 비어 있습니다.");
      return data;
    },
  );
  const chartHasEquity =
    chart.data?.some((point) => point.series_name === "equity") ?? false;
  const equity = useCursorQuery<EquityPoint>(
    ["evidence", runId, "equity"],
    async (after_seq) => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/equity",
        {
          params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
        },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("자본 Evidence 응답이 비어 있습니다.");
      return data;
    },
    chart.isSuccess && !chartHasEquity,
  );
  return { chart, equity };
}

export function useExecutions(runId: string, tradeId?: number) {
  return useCursorQuery<Execution>(
    ["evidence", runId, "executions", tradeId ?? "all"],
    async (after_seq) => {
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
    },
    tradeId === undefined || tradeId > 0,
  );
}

export function useDrawdownEpisodes(runId: string) {
  return useCursorQuery<DrawdownEpisode>(
    ["evidence", runId, "drawdown-episodes"],
    async (after_seq) => {
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
    },
  );
}

export function useOutcomeBuckets(runId: string) {
  return useCursorQuery<OutcomeBucket>(
    ["evidence", runId, "outcome-buckets"],
    async (after_seq) => {
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
    },
  );
}

export function useIntegrityChecks(runId: string) {
  return useCursorQuery<IntegrityCheck>(
    ["evidence", runId, "integrity-checks"],
    async (after_seq) => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/integrity-checks",
        {
          params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
        },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("무결성 Evidence 응답이 비어 있습니다.");
      return data;
    },
  );
}

export function useTradeDrawerEvidence(runId: string, tradeId: number | null) {
  const enabled = tradeId !== null;
  const funding = useCursorQuery<FundingSettlement>(
    ["evidence", runId, "funding", tradeId],
    async (after_seq) => {
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
    },
    enabled,
  );
  const features = useCursorQuery<TradeFeature>(
    ["evidence", runId, "trade-features", tradeId],
    async (after_seq) => {
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
    },
    enabled,
  );
  const candidates = useCursorQuery<CandidateEvent>(
    ["evidence", runId, "candidate-events", tradeId],
    async (after_seq) => {
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
    },
    enabled,
  );
  const positions = useCursorQuery<Position>(
    ["evidence", runId, "positions", tradeId],
    async (after_seq) => {
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
    },
    enabled,
  );
  return { funding, features, candidates, positions };
}

export function useChartEvidence(
  runId: string,
  selectedSeries: ReadonlySet<string> | null,
) {
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
  const definitions = useQuery({
    queryKey: ["evidence", runId, "indicator-definitions"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET(
        "/api/v1/runs/{run_id}/indicator-definitions",
        { params: { path: { run_id: runId } } },
      );
      if (error) throw apiRequestError(error);
      if (!data) throw new Error("지표 정의 목록 응답이 비어 있습니다.");
      return data as IndicatorDefinition[];
    },
  });
  const defaultSeries =
    definitions.data
      ?.filter((definition) => definition.series_kind === "indicator")
      .map((definition) => definition.indicator_key) ?? [];
  const selectedKeys = [...(selectedSeries ?? new Set(defaultSeries))].sort();
  const firstFeatureTime = candles.data?.data[0]?.close_time;
  const lastFeatureTime = candles.data?.data.at(-1)?.close_time;
  const indicatorQuery = useQuery({
    queryKey: [
      "evidence",
      runId,
      "indicator-snapshots",
      selectedKeys,
      firstFeatureTime,
      lastFeatureTime,
    ],
    queryFn: async (): Promise<IndicatorEvidencePage> => {
      const pages = await Promise.all(
        selectedKeys.map(async (indicatorKey) => {
          const page = await allPages<IndicatorSnapshot>(async (after_seq) => {
            const { data, error } = await apiClient.GET(
              "/api/v1/runs/{run_id}/indicator-snapshots",
              {
                params: {
                  path: { run_id: runId },
                  query: {
                    after_seq,
                    limit: 200,
                    indicator_key: indicatorKey,
                    feature_time_from: firstFeatureTime,
                    feature_time_to: lastFeatureTime,
                  },
                },
              },
            );
            if (error) throw apiRequestError(error);
            if (!data) throw new Error("지표 스냅샷 응답이 비어 있습니다.");
            return data;
          });
          return { indicatorKey, page };
        }),
      );
      return {
        rows: pages.flatMap(({ page }) => page.rows),
        truncated: pages.some(({ page }) => page.truncated),
        truncatedKeys: pages
          .filter(({ page }) => page.truncated)
          .map(({ indicatorKey }) => indicatorKey),
        limit: EVIDENCE_ROW_LIMIT,
        pageLimit: EVIDENCE_PAGE_LIMIT,
      };
    },
    enabled:
      selectedKeys.length > 0 &&
      firstFeatureTime !== undefined &&
      lastFeatureTime !== undefined,
  });
  const indicators = {
    ...indicatorQuery,
    data: indicatorQuery.data?.rows,
    evidence: indicatorQuery.data,
  };
  const signals = useSignals(runId);
  const candidates = useCandidateEvents(runId);
  const executions = useExecutions(runId);
  return { candles, definitions, indicators, signals, candidates, executions };
}

export function useSignals(runId: string) {
  return useCursorQuery<Signal>(["evidence", runId, "signals"], async (after_seq) => {
    const { data, error } = await apiClient.GET("/api/v1/runs/{run_id}/signals", {
      params: { path: { run_id: runId }, query: { after_seq, limit: 200 } },
    });
    if (error) throw apiRequestError(error);
    if (!data) throw new Error("신호 Evidence 응답이 비어 있습니다.");
    return data;
  });
}

export function useDecisions(runId: string) {
  return useCursorQuery<Decision>(
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
  return useCursorQuery<CandidateEvent>(
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
  return useCursorQuery<MissedOpportunity>(
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
  const conditional = useCursorQuery<ConditionalExpectancy>(
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
  const findings = useCursorQuery<Finding>(
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
