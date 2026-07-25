import {
  AreaSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  PriceScaleMode,
  type SeriesMarker,
  type UTCTimestamp,
} from "lightweight-charts";
import { Crosshair, LineChart as LineChartIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";

import type {
  ChartSummary,
  DrawdownEpisode,
  Execution,
} from "../../api/client";
import {
  useDrawdownEpisodes,
  useEquityEvidence,
  useExecutions,
} from "../../hooks/use-evidence";
import { formatDecimalString, formatMetric, formatTimestamp } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";
import { EvidenceError, EvidenceLoading } from "./evidence-state";

type EquityDatum = { time: UTCTimestamp; value: number };

function epochSeconds(value: string): UTCTimestamp {
  return Math.floor(new Date(value).getTime() / 1000) as UTCTimestamp;
}

function EquityChart({
  data,
  executions,
  markersVisible,
  logarithmic,
}: {
  data: EquityDatum[];
  executions: Execution[];
  markersVisible: boolean;
  logarithmic: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current || data.length === 0) return;
    const element = container.current;
    const chart = createChart(element, {
      width: element.clientWidth,
      height: 310,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(148,163,184,0.08)" },
        horzLines: { color: "rgba(148,163,184,0.08)" },
      },
      timeScale: { borderColor: "rgba(148,163,184,0.18)" },
      rightPriceScale: {
        borderColor: "rgba(148,163,184,0.18)",
        mode: logarithmic ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
      },
    });
    const series = chart.addSeries(AreaSeries, {
      lineColor: "#2dd4bf",
      topColor: "rgba(45,212,191,0.28)",
      bottomColor: "rgba(45,212,191,0.01)",
      lineWidth: 2,
    });
    series.setData(data);
    if (markersVisible) {
      const markers: SeriesMarker<UTCTimestamp>[] = executions.map((execution) => ({
        time: (Math.floor(new Date(execution.execution_ts).getTime() / 3_600_000) *
          3600) as UTCTimestamp,
        position: execution.side === "BUY" ? "belowBar" : "aboveBar",
        color: execution.side === "BUY" ? "#34d399" : "#fb7185",
        shape: execution.side === "BUY" ? "arrowUp" : "arrowDown",
        text: execution.trade_id ? `#${execution.trade_id}` : execution.side,
      }));
      createSeriesMarkers(series, markers);
    }
    chart.timeScale().fitContent();
    const resize = new ResizeObserver(() => {
      chart.applyOptions({ width: element.clientWidth });
    });
    resize.observe(element);
    return () => {
      resize.disconnect();
      chart.remove();
    };
  }, [data, executions, logarithmic, markersVisible]);

  return <div ref={container} className="h-[310px] w-full" aria-label="자본곡선" />;
}

function contributingTrades(value: DrawdownEpisode["contributing_trades_json"]): number[] {
  return Array.isArray(value)
    ? value.filter((item): item is number => typeof item === "number")
    : [];
}

const episodeColumn = createColumnHelper<DrawdownEpisode>();

function EpisodeTable({
  episodes,
  onSelectTrade,
}: {
  episodes: DrawdownEpisode[];
  onSelectTrade: (tradeId: number) => void;
}) {
  const columns = useMemo(
    () => [
      episodeColumn.accessor("start_ts", {
        header: "시작",
        cell: (info) => formatTimestamp(info.getValue()),
      }),
      episodeColumn.accessor("end_ts", {
        header: "저점",
        cell: (info) => formatTimestamp(info.getValue()),
      }),
      episodeColumn.accessor("recovery_ts", {
        header: "회복",
        cell: (info) => (info.getValue() ? formatTimestamp(info.getValue()!) : "미회복"),
      }),
      episodeColumn.accessor("depth_pct", {
        header: "깊이",
        cell: (info) =>
          formatMetric(info.getValue(), {
            style: "percent",
            maximumFractionDigits: 2,
          }),
      }),
      episodeColumn.accessor("duration_seconds", {
        header: "기간",
        cell: (info) => `${Math.round(info.getValue() / 3600)}h`,
      }),
      episodeColumn.accessor("contributing_trades_json", {
        header: "기여 거래",
        cell: (info) => (
          <div className="flex max-w-72 flex-wrap gap-1">
            {contributingTrades(info.getValue()).map((tradeId) => (
              <button key={tradeId} type="button" onClick={() => onSelectTrade(tradeId)}>
                <Badge variant="outline">#{tradeId}</Badge>
              </button>
            ))}
          </div>
        ),
      }),
    ],
    [onSelectTrade],
  );
  const table = useReactTable({
    data: [...episodes].sort((a, b) => a.depth_pct - b.depth_pct),
    columns,
    getCoreRowModel: getCoreRowModel(),
  });
  return (
    <Table>
      <TableHeader>
        {table.getHeaderGroups().map((group) => (
          <TableRow key={group.id}>
            {group.headers.map((header) => (
              <TableHead key={header.id}>
                {flexRender(header.column.columnDef.header, header.getContext())}
              </TableHead>
            ))}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow key={row.id}>
            {row.getVisibleCells().map((cell) => (
              <TableCell key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function EquityDrawdownTab({
  runId,
  onSelectTrade,
}: {
  runId: string;
  onSelectTrade: (tradeId: number) => void;
}) {
  const { chart, equity } = useEquityEvidence(runId);
  const executions = useExecutions(runId);
  const episodes = useDrawdownEpisodes(runId);
  const [markersVisible, setMarkersVisible] = useState(true);
  const [logarithmic, setLogarithmic] = useState(false);

  const equitySeries = useMemo(() => {
    const stored = (chart.data ?? []).filter((point) => point.series_name === "equity");
    if (stored.length > 0) {
      return stored.flatMap((point) =>
        point.value === null
          ? []
          : [{ time: epochSeconds(point.bucket_ts), value: point.value }],
      );
    }
    return (equity.data ?? []).map((point) => ({
      time: epochSeconds(point.ts),
      value: Number(point.total_equity),
    }));
  }, [chart.data, equity.data]);
  const drawdownSeries = useMemo(
    () => {
      const stored = (chart.data ?? [])
        .filter(
          (point): point is ChartSummary & { value: number } =>
            point.series_name === "drawdown" && point.value !== null,
        )
        .map((point) => ({ ts: point.bucket_ts, value: point.value * 100 }));
      return stored.length > 0
        ? stored
        : (equity.data ?? []).map((point) => ({
            ts: point.ts,
            value: point.drawdown_pct * 100,
          }));
    },
    [chart.data, equity.data],
  );

  if (chart.isLoading || executions.isLoading || episodes.isLoading) {
    return <EvidenceLoading />;
  }
  const error = chart.error ?? executions.error ?? episodes.error;
  if (error) return <EvidenceError error={error} />;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-row items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <LineChartIcon className="h-4 w-4 text-teal-400" />
              자본곡선
            </CardTitle>
            <CardDescription>
              CHART_SUMMARY 우선 · {equitySeries.length.toLocaleString()}개 저장 포인트
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={logarithmic ? "secondary" : "outline"}
              onClick={() => setLogarithmic((value) => !value)}
            >
              로그축
            </Button>
            <Button
              size="sm"
              variant={markersVisible ? "secondary" : "outline"}
              onClick={() => setMarkersVisible((value) => !value)}
            >
              <Crosshair className="mr-1.5 h-3.5 w-3.5" />
              매매 마커
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {equitySeries.length ? (
            <EquityChart
              data={equitySeries}
              executions={executions.data ?? []}
              markersVisible={markersVisible}
              logarithmic={logarithmic}
            />
          ) : (
            <p className="py-24 text-center text-sm text-muted-foreground">
              자본곡선 포인트가 없습니다.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>드로다운</CardTitle>
          <CardDescription>자본곡선과 동일한 UTC 시간축입니다.</CardDescription>
        </CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={drawdownSeries}>
              <defs>
                <linearGradient id="dd-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#fb7185" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#fb7185" stopOpacity={0.55} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" opacity={0.12} />
              <XAxis dataKey="ts" hide />
              <YAxis
                width={52}
                tickFormatter={(value: number) => `${value.toFixed(1)}%`}
              />
              <Tooltip
                labelFormatter={(value) => formatTimestamp(String(value))}
                formatter={(value) => [`${Number(value).toFixed(2)}%`, "DD"]}
              />
              <Area
                type="stepAfter"
                dataKey="value"
                stroke="#fb7185"
                fill="url(#dd-fill)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>드로다운 사건</CardTitle>
          <CardDescription>
            저장된 DRAWDOWN_RUNUP_EPISODE · 깊이순 · 금액은 문자열 그대로 표시
          </CardDescription>
        </CardHeader>
        <CardContent>
          {episodes.data?.length ? (
            <EpisodeTable episodes={episodes.data} onSelectTrade={onSelectTrade} />
          ) : (
            <p className="py-12 text-center text-sm text-muted-foreground">
              드로다운 사건이 없습니다.
            </p>
          )}
          {episodes.data?.[0] && (
            <p className="mt-3 text-[10px] text-muted-foreground">
              첫 사건 peak {formatDecimalString(episodes.data[0].peak_equity)} · trough{" "}
              {formatDecimalString(episodes.data[0].trough_equity)}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
