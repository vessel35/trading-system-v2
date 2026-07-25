import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app";
import { CatalogFilterProvider } from "./contexts/catalog-filters";
import { ComparisonBasketProvider } from "./contexts/comparison-basket";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const root = document.getElementById("root");
if (!root) {
  throw new Error("Root element is unavailable");
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <CatalogFilterProvider>
        <ComparisonBasketProvider>
          <App />
        </ComparisonBasketProvider>
      </CatalogFilterProvider>
    </QueryClientProvider>
  </StrictMode>,
);
