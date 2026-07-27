import {
  AlertTriangle,
  Database,
  Info,
  ShieldCheck,
} from "lucide-react";

import type { InventoryItem } from "../api/client";
import { Badge } from "../components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { useInventory } from "../hooks/use-inventory";
import { formatTimestamp } from "../lib/utils";

const DATA_SOURCE = "crypto_data.ohlcv_futures";
const coverageFormatter = new Intl.NumberFormat("ko-KR", {
  style: "percent",
  maximumFractionDigits: 2,
});

function period(item: InventoryItem) {
  if (!item.available_from || !item.available_to) return "데이터 없음";
  return `${formatTimestamp(item.available_from)} ~ ${formatTimestamp(item.available_to)}`;
}

function Coverage({ item }: { item: InventoryItem }) {
  const label = coverageFormatter.format(item.coverage_ratio);
  return (
    <div className="flex min-w-32 items-center gap-2">
      <progress
        aria-label={`${item.symbol} 커버리지`}
        aria-valuetext={label}
        className="h-1.5 w-20 accent-teal-400"
        max={1}
        value={item.coverage_ratio}
      />
      <Badge variant="outline" className="min-w-16 justify-center tabular">
        {label}
      </Badge>
    </div>
  );
}

function InventoryLoading() {
  return (
    <div aria-label="데이터 인벤토리 로딩" className="space-y-2 p-4">
      {Array.from({ length: 5 }, (_, index) => (
        <Skeleton key={index} className="h-12 w-full" />
      ))}
    </div>
  );
}

export function DataPage() {
  const inventory = useInventory(DATA_SOURCE);
  const items = inventory.data?.items ?? [];

  return (
    <div className="mx-auto max-w-[1500px] space-y-4 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-teal-300" />
            <h1 className="text-xl font-semibold tracking-tight">시장 데이터 인벤토리</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            백테스트가 조회하는 심볼별 1분봉 기간과 연속 커버리지를 확인합니다.
          </p>
        </div>
        <Badge variant="success" className="gap-1.5">
          <ShieldCheck className="h-3 w-3" />
          읽기 전용
        </Badge>
      </div>

      <div
        role="note"
        className="flex items-start gap-2 rounded-lg border border-teal-500/20 bg-teal-500/10 p-3 text-sm text-teal-100"
      >
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <p>
          crypto_data는 1분봉만 저장하며 상위 타임프레임은 연속집계입니다. 수집과
          backfill은 후속 단계에서 제공할 예정입니다.
        </p>
      </div>

      <Card className="overflow-hidden shadow-glow">
        <CardHeader>
          <CardTitle>OHLCV 커버리지</CardTitle>
          <CardDescription className="font-mono">{DATA_SOURCE}</CardDescription>
        </CardHeader>

        {inventory.isLoading ? (
          <InventoryLoading />
        ) : inventory.isError ? (
          <CardContent className="grid min-h-72 place-items-center p-8 text-center">
            <div>
              <AlertTriangle className="mx-auto h-8 w-8 text-red-400" />
              <p className="mt-3 font-medium">데이터 인벤토리를 불러오지 못했습니다.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {inventory.error.message}
              </p>
              <Button className="mt-4" onClick={() => void inventory.refetch()}>
                다시 시도
              </Button>
            </div>
          </CardContent>
        ) : items.length === 0 ? (
          <CardContent className="grid min-h-72 place-items-center p-8 text-center">
            <div>
              <Database className="mx-auto h-8 w-8 text-muted-foreground" />
              <p className="mt-3 font-medium">저장된 1분봉 데이터가 없습니다.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                이 데이터 소스에서 조회 가능한 심볼이 없습니다.
              </p>
            </div>
          </CardContent>
        ) : (
          <Table>
            <TableHeader className="bg-card">
              <TableRow>
                <TableHead>심볼</TableHead>
                <TableHead>거래소</TableHead>
                <TableHead>타임프레임</TableHead>
                <TableHead>기간</TableHead>
                <TableHead className="text-right">건수</TableHead>
                <TableHead className="text-right">예상 1m</TableHead>
                <TableHead className="text-right">누락 갭</TableHead>
                <TableHead>커버리지</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={`${item.symbol}:${item.exchange}`}>
                  <TableCell className="font-medium">{item.symbol}</TableCell>
                  <TableCell>{item.exchange}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{item.timeframe}</Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs tabular text-muted-foreground">
                    {period(item)}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {item.row_count.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {item.expected_1m_rows.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    <span
                      className={
                        item.missing_1m_rows > 0 ? "text-amber-300" : "text-emerald-300"
                      }
                    >
                      {item.missing_1m_rows.toLocaleString()}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Coverage item={item} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
