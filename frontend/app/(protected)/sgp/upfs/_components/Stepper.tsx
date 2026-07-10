"use client";

import { Check } from "lucide-react";

type StepperProps = {
  steps: string[];
  current: number;
  /** Passo mais avançado já alcançado (define quais são clicáveis). */
  furthest: number;
  onStepClick: (index: number) => void;
};

/** Stepper horizontal: completos com check (clicáveis), atual em destaque, futuros desabilitados. */
export function Stepper({
  steps,
  current,
  furthest,
  onStepClick,
}: StepperProps) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-3">
      {steps.map((label, index) => {
        const isCurrent = index === current;
        const isCompleted = index < current;
        const isReachable = index <= furthest;

        return (
          <li key={label} className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => isReachable && onStepClick(index)}
              disabled={!isReachable}
              aria-current={isCurrent ? "step" : undefined}
              className={`flex items-center gap-2 rounded-md px-2 py-1 text-sm transition-colors ${
                isReachable
                  ? "cursor-pointer"
                  : "cursor-not-allowed opacity-50"
              } ${
                isCurrent
                  ? "font-semibold text-primary"
                  : "text-text-muted hover:text-text"
              }`}
            >
              <span
                aria-hidden="true"
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  isCurrent
                    ? "bg-primary text-surface"
                    : isCompleted
                      ? "bg-success-bg text-success-text"
                      : "bg-surface-muted text-text-muted"
                }`}
              >
                {isCompleted ? <Check className="h-3.5 w-3.5" /> : index + 1}
              </span>
              <span className="whitespace-nowrap">{label}</span>
            </button>

            {index < steps.length - 1 && (
              <span aria-hidden="true" className="text-text-muted/50">
                ›
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
