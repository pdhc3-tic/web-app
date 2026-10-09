"use client";

import { useId } from "react";
import { ErrorIcon } from "@/app/components/icons";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { ODS_OPTIONS, odsShortLabel } from "@/app/lib/metas";

export type OdsPickerProps = {
  /** IDs de ODS selecionados (1–17). */
  value: number[];
  onChange: (value: number[]) => void;
  error?: string;
  disabled?: boolean;
};

const checkboxClass =
  "h-4 w-4 shrink-0 cursor-pointer accent-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-70";

const itemClass =
  "flex items-start gap-2 rounded-md px-2 py-1.5 text-sm text-text transition-colors hover:bg-surface-muted has-[:disabled]:hover:bg-transparent";

/**
 * Seleção múltipla dos ODS vinculados à Meta.
 *
 * O <Select> do design system é single-select, e são 17 opções fixas e curtas —
 * um grupo de checkboxes em fieldset/legend resolve sem componente novo e já
 * nasce acessível (navegação por Tab, leitura do grupo pelo leitor de tela).
 */
export function OdsPicker({
  value,
  onChange,
  error,
  disabled = false,
}: OdsPickerProps) {
  const id = useId();
  const errorId = error ? `${id}-error` : undefined;
  const selected = new Set(value);

  function toggle(odsId: number) {
    // Mantém a ordem crescente para que o payload não dependa da ordem de clique.
    const next = selected.has(odsId)
      ? value.filter((v) => v !== odsId)
      : [...value, odsId].sort((a, b) => a - b);
    onChange(next);
  }

  return (
    <fieldset
      className="flex flex-col gap-1"
      aria-describedby={errorId}
      aria-invalid={error ? true : undefined}
      data-testid="meta-form-ods"
    >
      <legend className="text-label font-medium leading-[1.2] text-text">
        ODS vinculados
      </legend>

      <p className="text-2xs text-text-muted">
        Objetivos de Desenvolvimento Sustentável associados a esta Meta.
      </p>

      <div
        className={`mt-1 grid max-h-56 grid-cols-1 gap-0.5 overflow-y-auto rounded-md border p-1 sm:grid-cols-2 ${
          error ? "border-error-text" : "border-border"
        }`}
      >
        {ODS_OPTIONS.map((ods) => {
          const inputId = `${id}-ods-${ods.id}`;
          return (
            <label key={ods.id} htmlFor={inputId} className={itemClass}>
              <input
                id={inputId}
                type="checkbox"
                className={`${checkboxClass} mt-0.5`}
                checked={selected.has(ods.id)}
                disabled={disabled}
                onChange={() => toggle(ods.id)}
              />
              <span className="leading-snug">{ods.label}</span>
            </label>
          );
        })}
      </div>

      {value.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {value.map((odsId) => (
            <Chip
              key={odsId}
              title={ODS_OPTIONS.find((o) => o.id === odsId)?.label}
            >
              {odsShortLabel(odsId)}
            </Chip>
          ))}
        </div>
      )}

      {error && (
        <span
          id={errorId}
          role="alert"
          className="inline-flex items-center gap-1 text-2xs text-error-text"
        >
          <ErrorIcon className="h-3 w-3 shrink-0" />
          {error}
        </span>
      )}
    </fieldset>
  );
}
