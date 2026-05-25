import type { LucideIcon } from "lucide-react";
import { Sparkles } from "lucide-react";
import { PageHeader } from "./PageHeader";

type ModulePlaceholderProps = {
  shortName: string;
  fullName: string;
  description: string;
  Icon: LucideIcon;
  features?: string[];
};

export function ModulePlaceholder({
  shortName,
  fullName,
  description,
  Icon,
  features,
}: ModulePlaceholderProps) {
  return (
    <>
      <PageHeader>
        <div className="flex items-baseline gap-2 min-w-0">
          <h1 className="text-base font-semibold text-text truncate">
            {shortName}
          </h1>
          <span className="hidden sm:inline text-xs text-text-muted truncate">
            {fullName}
          </span>
        </div>
      </PageHeader>

      <div className="max-w-2xl mx-auto pt-8 sm:pt-12">
        <div className="relative">
          <div
            aria-hidden="true"
            className="absolute -top-12 -left-12 h-64 w-64 rounded-full bg-gradient-to-br from-primary/10 to-transparent blur-2xl"
          />
          <div
            aria-hidden="true"
            className="absolute -top-8 right-0 h-48 w-48 rounded-full bg-gradient-to-tl from-accent-ocre/10 to-transparent blur-2xl"
          />

          <div className="relative">
            <div className="flex items-center justify-center h-16 w-16 rounded-2xl bg-gradient-to-br from-primary to-secondary text-surface shadow-lg shadow-primary/20">
              <Icon className="h-7 w-7" aria-hidden="true" strokeWidth={1.75} />
            </div>

            <div className="mt-10">
              <span className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-warning-bg border border-warning-text/20">
                <Sparkles
                  className="h-3 w-3 text-warning-text"
                  aria-hidden="true"
                />
                <span className="text-[10px] font-medium uppercase tracking-wider text-warning-text">
                  Em desenvolvimento
                </span>
              </span>
            </div>

            <h2 className="mt-4 text-3xl sm:text-4xl font-semibold leading-tight text-text tracking-tight">
              {fullName}
            </h2>

            <p className="mt-4 text-base text-text-muted leading-relaxed max-w-xl">
              {description}
            </p>
          </div>
        </div>

        {features && features.length > 0 && (
          <div className="mt-12 pt-8 border-t border-border">
            <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-text-muted mb-4">
              O que vem por aí
            </p>
            <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-3">
              {features.map((f) => (
                <li
                  key={f}
                  className="flex items-start gap-2.5 text-sm text-text leading-relaxed"
                >
                  <span
                    aria-hidden="true"
                    className="mt-1.5 h-1 w-1 rounded-full bg-primary shrink-0"
                  />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </>
  );
}
