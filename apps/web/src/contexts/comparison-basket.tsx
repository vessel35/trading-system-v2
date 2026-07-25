import {
  createContext,
  type PropsWithChildren,
  useContext,
  useMemo,
  useState,
} from "react";

import type { RunListItem } from "../api/client";

export type ComparisonItem = Pick<
  RunListItem,
  "run_id" | "run_name" | "strategy_name" | "symbol" | "timeframe"
>;

interface ComparisonBasketValue {
  items: ComparisonItem[];
  add: (items: ComparisonItem[]) => void;
  remove: (runId: string) => void;
  clear: () => void;
  includes: (runId: string) => boolean;
}

const ComparisonBasketContext = createContext<ComparisonBasketValue | null>(null);

export function ComparisonBasketProvider({ children }: PropsWithChildren) {
  const [items, setItems] = useState<ComparisonItem[]>([]);

  const value = useMemo<ComparisonBasketValue>(
    () => ({
      items,
      add: (incoming) =>
        setItems((current) => {
          const merged = new Map(current.map((item) => [item.run_id, item]));
          incoming.forEach((item) => merged.set(item.run_id, item));
          return [...merged.values()];
        }),
      remove: (runId) =>
        setItems((current) => current.filter((item) => item.run_id !== runId)),
      clear: () => setItems([]),
      includes: (runId) => items.some((item) => item.run_id === runId),
    }),
    [items],
  );

  return (
    <ComparisonBasketContext.Provider value={value}>
      {children}
    </ComparisonBasketContext.Provider>
  );
}

export function useComparisonBasket(): ComparisonBasketValue {
  const value = useContext(ComparisonBasketContext);
  if (!value) {
    throw new Error("useComparisonBasket must be used within ComparisonBasketProvider");
  }
  return value;
}
