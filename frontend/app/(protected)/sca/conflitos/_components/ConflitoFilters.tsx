"use client";

import { X } from "lucide-react";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { ENTIDADE_LABEL, STATUS_LABEL } from "@/app/lib/conflitos";

export type ConflitoFiltersValue = {
  /** ConflictLog.Status. "" = todos. */
  status: string;
  /** "true" | "false" | "" — BooleanFilter do backend. */
  sensivel: string;
  /** upf | member | activity. "" = todas. */
  entidade: string;
};

export const FILTROS_VAZIOS: ConflitoFiltersValue = {
  status: "",
  sensivel: "",
  entidade: "",
};

/** Valores aceitos pelo backend; a página também os usa para sanear a URL. */
export const STATUS_VALIDOS = Object.keys(STATUS_LABEL);
export const ENTIDADES_VALIDAS = Object.keys(ENTIDADE_LABEL);
export const SENSIVEL_VALIDOS = ["true", "false"];

const STATUS_OPTIONS: SelectOption[] = STATUS_VALIDOS.map((value) => ({
  value,
  label: STATUS_LABEL[value as keyof typeof STATUS_LABEL],
}));

const ENTIDADE_OPTIONS: SelectOption[] = ENTIDADES_VALIDAS.map((value) => ({
  value,
  label: ENTIDADE_LABEL[value as keyof typeof ENTIDADE_LABEL],
}));

const SENSIVEL_OPTIONS: SelectOption[] = [
  { value: "true", label: "Somente sensíveis" },
  { value: "false", label: "Somente não sensíveis" },
];

type Props = {
  value: ConflitoFiltersValue;
  onChange: (patch: Partial<ConflitoFiltersValue>) => void;
  onClear: () => void;
};

export function ConflitoFilters({ value, onChange, onClear }: Props) {
  const temFiltro =
    value.status !== "" || value.sensivel !== "" || value.entidade !== "";

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="min-w-44 flex-1">
        <Select
          id="conflitos-filtro-status"
          label="Status"
          options={[{ value: "", label: "Todos os status" }, ...STATUS_OPTIONS]}
          value={value.status}
          onChange={(v) => onChange({ status: v })}
          placeholder="Todos os status"
        />
      </div>

      <div className="min-w-44 flex-1">
        <Select
          id="conflitos-filtro-sensivel"
          label="Sensibilidade"
          options={[{ value: "", label: "Todos os campos" }, ...SENSIVEL_OPTIONS]}
          value={value.sensivel}
          onChange={(v) => onChange({ sensivel: v })}
          placeholder="Todos os campos"
        />
      </div>

      <div className="min-w-44 flex-1">
        <Select
          id="conflitos-filtro-entidade"
          label="Entidade"
          options={[{ value: "", label: "Todas as entidades" }, ...ENTIDADE_OPTIONS]}
          value={value.entidade}
          onChange={(v) => onChange({ entidade: v })}
          placeholder="Todas as entidades"
        />
      </div>

      {temFiltro && (
        <button
          type="button"
          onClick={onClear}
          data-testid="conflitos-limpar-filtros"
          className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md px-3 text-sm text-text-muted transition-colors hover:bg-surface-muted hover:text-text"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
          Limpar filtros
        </button>
      )}
    </div>
  );
}
