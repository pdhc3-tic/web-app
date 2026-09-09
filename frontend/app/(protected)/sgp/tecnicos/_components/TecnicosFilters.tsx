"use client";

import { X } from "lucide-react";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { Input } from "@/app/components/ui/Input/Input";

export type TecnicosFiltersValue = {
  territorio: string;
  osc: string;
  papel: string;
  ativo: string;
};

export const EMPTY_FILTERS: TecnicosFiltersValue = {
  territorio: "",
  osc: "",
  papel: "",
  ativo: "",
};

const ATIVO_OPTIONS: SelectOption[] = [
  { value: "true", label: "Ativo" },
  { value: "false", label: "Inativo" },
];

type Props = {
  filters: TecnicosFiltersValue;
  territorioOptions: SelectOption[];
  oscOptions: SelectOption[];
  onChange: (patch: Partial<TecnicosFiltersValue>) => void;
  onClear: () => void;
};

export function TecnicosFilters({
  filters,
  territorioOptions,
  oscOptions,
  onChange,
  onClear,
}: Props) {
  const hasActive = Object.values(filters).some((v) => v !== "");

  return (
    <div className="flex flex-wrap items-end gap-3">
      <Select
        label="Território"
        options={territorioOptions}
        value={filters.territorio}
        onChange={(v) => onChange({ territorio: v })}
        placeholder="Todos"
      />
      <Select
        label="OSC"
        options={oscOptions}
        value={filters.osc}
        onChange={(v) => onChange({ osc: v })}
        placeholder="Todas"
      />
      <Input
        label="Papel"
        value={filters.papel}
        onChange={(e) => onChange({ papel: e.target.value })}
        placeholder="Filtrar por papel..."
      />
      <Select
        label="Situação"
        options={ATIVO_OPTIONS}
        value={filters.ativo}
        onChange={(v) => onChange({ ativo: v })}
        placeholder="Todas"
      />
      {hasActive && (
        <button
          type="button"
          onClick={onClear}
          className="flex items-center gap-1 text-sm text-text-muted hover:text-text"
        >
          <X className="h-4 w-4" />
          Limpar
        </button>
      )}
    </div>
  );
}
