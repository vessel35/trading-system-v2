import { Redirect, Route, Switch } from "wouter";

import { AppShell } from "./components/app-shell";
import { CatalogPage } from "./pages/catalog-page";
import { RunSummaryPage } from "./pages/run-summary-page";

export function App() {
  return (
    <Switch>
      <Route path="/runs/:runId">
        {(params) => (
          <AppShell>
            <RunSummaryPage runId={decodeURIComponent(params.runId)} />
          </AppShell>
        )}
      </Route>
      <Route path="/runs">
        <AppShell>
          <CatalogPage />
        </AppShell>
      </Route>
      <Route>
        <Redirect to="/runs" replace />
      </Route>
    </Switch>
  );
}
