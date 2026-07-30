import { AlertTriangle, CircleHelp, Info } from "lucide-react";

import {
  researchHelpById,
  type ResearchHelpId,
} from "../lib/research-help";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";

interface ResearchHelpDialogProps {
  helpId: ResearchHelpId;
}

export function ResearchHelpDialog({ helpId }: ResearchHelpDialogProps) {
  const help = researchHelpById[helpId];

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 gap-1.5 px-2 text-muted-foreground"
          aria-label={help.triggerAriaLabel}
        >
          <CircleHelp className="h-4 w-4" aria-hidden="true" />
          도움말
        </Button>
      </DialogTrigger>
      <DialogContent className="top-[5vh] max-h-[90vh] max-w-3xl overflow-hidden">
        <div className="space-y-1 pr-8">
          <DialogTitle>{help.title}</DialogTitle>
          <DialogDescription className="leading-relaxed">
            {help.overview}
          </DialogDescription>
        </div>

        <div className="space-y-5 overflow-y-auto pr-2 text-sm">
          <section className="space-y-2" aria-labelledby={`${helpId}-concept-heading`}>
            <h2
              id={`${helpId}-concept-heading`}
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

          <section aria-labelledby={`${helpId}-fields-heading`}>
            <h2
              id={`${helpId}-fields-heading`}
              className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              폼 항목
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {help.fields.map((field) => (
                <article
                  key={field.name}
                  className="space-y-2 rounded-lg border bg-muted/20 p-4"
                >
                  <div>
                    <h3 className="text-sm font-semibold text-teal-200">
                      {field.label}
                    </h3>
                    <code className="mt-1 block text-xs text-muted-foreground">
                      {field.name}
                    </code>
                  </div>
                  <p className="text-xs leading-relaxed">{field.description}</p>
                </article>
              ))}
            </div>
          </section>

          {help.example && (
            <section
              className="flex items-start gap-3 rounded-lg border border-teal-500/20 bg-teal-500/5 p-4"
              aria-label="예시"
            >
              <Info
                className="mt-0.5 h-4 w-4 shrink-0 text-teal-300"
                aria-hidden="true"
              />
              <p className="text-xs leading-relaxed">{help.example}</p>
            </section>
          )}

          {help.note && (
            <section
              className="flex items-start gap-3 rounded-lg border border-blue-500/20 bg-blue-500/5 p-4"
              aria-label="현재 지원 상태"
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
