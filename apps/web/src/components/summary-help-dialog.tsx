import { AlertTriangle, Info } from "lucide-react";
import { useCallback } from "react";

import {
  summaryHelpBySection,
  type SummaryHelpSectionId,
} from "../lib/summary-help";
import { cn } from "../lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "./ui/dialog";

export interface SummaryHelpTarget {
  sectionId: SummaryHelpSectionId;
  /** The item to scroll to and highlight, or null to open at the top. */
  itemId: string | null;
}

interface SummaryHelpDialogProps {
  target: SummaryHelpTarget | null;
  onClose: () => void;
}

export function SummaryHelpDialog({ target, onClose }: SummaryHelpDialogProps) {
  const focusedId = target?.itemId ?? null;
  const focusRef = useCallback((node: HTMLElement | null) => {
    if (node && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ block: "center" });
    }
  }, []);

  if (!target) return null;
  const help = summaryHelpBySection[target.sectionId];

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="top-[5vh] max-h-[90vh] max-w-3xl overflow-hidden">
        <div className="space-y-1 pr-8">
          <DialogTitle>{help.title}</DialogTitle>
          <DialogDescription className="leading-relaxed">
            {help.overview}
          </DialogDescription>
        </div>

        <div className="space-y-5 overflow-y-auto pr-2 text-sm">
          <section
            className="space-y-2"
            aria-labelledby={`${target.sectionId}-concept-heading`}
          >
            <h2
              id={`${target.sectionId}-concept-heading`}
              className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              먼저 알아둘 개념
            </h2>
            {help.concepts.map((concept) => (
              <p key={concept} className="leading-relaxed">
                {concept}
              </p>
            ))}
          </section>

          <section aria-labelledby={`${target.sectionId}-item-heading`}>
            <h2
              id={`${target.sectionId}-item-heading`}
              className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              표시되는 값
            </h2>
            <div className="space-y-3">
              {help.items.map((item) => {
                const focused = item.id === focusedId;
                return (
                  <article
                    key={item.id}
                    ref={focused ? focusRef : undefined}
                    data-focused={focused ? "true" : undefined}
                    aria-current={focused ? "true" : undefined}
                    className={cn(
                      "space-y-2 rounded-lg border bg-muted/20 p-4",
                      focused && "border-teal-400/60 bg-teal-500/10",
                    )}
                  >
                    <div>
                      <h3 className="text-sm font-semibold text-teal-200">
                        {item.label}
                      </h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {item.term}
                      </p>
                    </div>
                    <p className="text-xs leading-relaxed">{item.meaning}</p>
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      {item.reading}
                    </p>
                    <p className="text-xs leading-relaxed">
                      <span className="text-muted-foreground">통과 기준 · </span>
                      {item.criterion}
                    </p>
                  </article>
                );
              })}
            </div>
          </section>

          {help.note && (
            <section
              className="flex items-start gap-3 rounded-lg border border-blue-500/20 bg-blue-500/5 p-4"
              aria-label="함께 보면 좋은 값"
            >
              <Info
                className="mt-0.5 h-4 w-4 shrink-0 text-blue-300"
                aria-hidden="true"
              />
              <p className="text-xs leading-relaxed">{help.note}</p>
            </section>
          )}

          {help.caution && (
            <section
              className="flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-4"
              aria-label="주의"
            >
              <AlertTriangle
                className="mt-0.5 h-4 w-4 shrink-0 text-amber-300"
                aria-hidden="true"
              />
              <p className="text-xs leading-relaxed">{help.caution}</p>
            </section>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
