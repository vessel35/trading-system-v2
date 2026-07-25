import {
  createContext,
  type PropsWithChildren,
  useContext,
  useMemo,
  useState,
} from "react";

import type { RunQuery } from "../api/client";

export type CatalogFilters = Pick<
  RunQuery,
  | "strategy_id"
  | "symbol"
  | "timeframe"
  | "exchange"
  | "market_type"
  | "status"
  | "decision_route"
  | "gate_passed"
  | "tag_type"
  | "tag_value"
  | "period_start_from"
  | "period_end_to"
>;

const initialFilters: CatalogFilters = {};

interface CatalogFilterContextValue {
  filters: CatalogFilters;
  updateFilters: (patch: Partial<CatalogFilters>) => void;
  resetFilters: () => void;
  activeCount: number;
}

const CatalogFilterContext = createContext<CatalogFilterContextValue | null>(null);

export function CatalogFilterProvider({ children }: PropsWithChildren) {
  const [filters, setFilters] = useState<CatalogFilters>(initialFilters);

  const value = useMemo<CatalogFilterContextValue>(
    () => ({
      filters,
      updateFilters: (patch) =>
        setFilters((current) => ({
          ...current,
          ...patch,
        })),
      resetFilters: () => setFilters(initialFilters),
      activeCount: Object.values(filters).filter(
        (value) => value !== undefined && value !== null && value !== "",
      ).length,
    }),
    [filters],
  );

  return (
    <CatalogFilterContext.Provider value={value}>
      {children}
    </CatalogFilterContext.Provider>
  );
}

export function useCatalogFilters(): CatalogFilterContextValue {
  const value = useContext(CatalogFilterContext);
  if (!value) {
    throw new Error("useCatalogFilters must be used within CatalogFilterProvider");
  }
  return value;
}
