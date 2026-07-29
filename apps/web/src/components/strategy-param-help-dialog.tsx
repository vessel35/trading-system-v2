import { CircleHelp } from "lucide-react";

import { strategyParamHelpById } from "../lib/strategy-param-help";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";

interface StrategyParamHelpDialogProps {
  strategyId: string;
}

export function StrategyParamHelpDialog({
  strategyId,
}: StrategyParamHelpDialogProps) {
  const help = strategyParamHelpById[strategyId];
  if (!help) return null;

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 gap-1.5 px-2 text-muted-foreground"
          aria-label="수동 자금 관리 도움말"
        >
          <CircleHelp className="h-4 w-4" aria-hidden="true" />
          도움말
        </Button>
      </DialogTrigger>
      <DialogContent className="top-[5vh] max-h-[90vh] max-w-4xl overflow-hidden">
        <div className="space-y-1 pr-8">
          <DialogTitle>
            수동 자금 관리 도움말 · {help.displayName}
          </DialogTitle>
          <DialogDescription className="leading-relaxed">
            {help.overview}
          </DialogDescription>
        </div>

        <div className="space-y-5 overflow-y-auto pr-2 text-sm">
          <section aria-labelledby="strategy-parameter-heading">
            <h2
              id="strategy-parameter-heading"
              className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              수동 정책 파라미터
            </h2>
            <div className="grid gap-3 lg:grid-cols-3">
              {help.parameters.map((parameter) => (
                <article
                  key={parameter.name}
                  className="space-y-3 rounded-lg border bg-muted/20 p-4"
                >
                  <div>
                    <h3 className="font-mono text-sm font-semibold text-teal-200">
                      {parameter.name}
                    </h3>
                    <p className="mt-1 font-mono text-xs tabular-nums text-muted-foreground">
                      {parameter.defaultAndRange}
                    </p>
                  </div>
                  <p className="text-xs leading-relaxed">{parameter.meaning}</p>
                  <div className="space-y-1.5 font-mono text-xs leading-relaxed tabular-nums">
                    {parameter.formulas.map((formula) => (
                      <code
                        key={formula}
                        className="block whitespace-normal rounded bg-background/70 px-2 py-1.5"
                      >
                        {formula}
                      </code>
                    ))}
                  </div>
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {parameter.guidance}
                  </p>
                </article>
              ))}
            </div>
          </section>

          <section
            className="space-y-2 rounded-lg border border-teal-500/20 bg-teal-500/5 p-4"
            aria-labelledby="sizing-help-heading"
          >
            <h2 id="sizing-help-heading" className="text-sm font-semibold">
              사이징 참고
            </h2>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {help.sizing.description}
            </p>
            <div className="space-y-1.5 font-mono text-xs leading-relaxed tabular-nums">
              {help.sizing.formulas.map((formula) => (
                <code
                  key={formula}
                  className="block whitespace-normal rounded bg-background/70 px-2 py-1.5"
                >
                  {formula}
                </code>
              ))}
            </div>
          </section>

          <section
            className="space-y-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-4"
            aria-labelledby="combined-example-heading"
          >
            <h2 id="combined-example-heading" className="text-sm font-semibold">
              종합 예시
            </h2>
            <p className="font-mono text-xs leading-relaxed tabular-nums text-muted-foreground">
              {help.example.input}
            </p>
            <ol className="list-decimal space-y-2 pl-8 font-mono text-xs leading-relaxed tabular-nums marker:text-amber-300">
              {help.example.steps.map((step) => (
                <li key={step} className="rounded bg-background/70 px-3 py-2">
                  {step}
                </li>
              ))}
            </ol>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
