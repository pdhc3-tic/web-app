"use client";

import { Search, X } from "lucide-react";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import type { StatusUpfFilter } from "@/app/lib/upfs";

const fieldLabelClass = "text-label font-medium text-text leading-[1.2]";

export type UpfsFiltersValue = {
  search: string;
  municipio: string;
  territorio: string;
  projeto: string;
  status: StatusUpfFilter;
  cadastradoDe: string;
  cadastradoAte: string;
};

type UpfsFiltersProps = {
  value: UpfsFiltersValue;
  onChange: (patch: Partial<UpfsFiltersValue>) => void;
  onClear: () => void;
  hasActiveFilters: boolean;
  municipioOptions: SelectOption[];
  territorioOptions: SelectOption[];
  optionsLoading: boolean;
};

const STATUS_SEGMENTS: { value: StatusUpfFilter; label: string }[] = [
  { value: "ativas", label: "Ativas" },
  { value: "inativas", label: "Inativas" },
  { value: "todas", label: "Todas" },
];

// Projeto ainda não tem endpoint público de listagem — mantemos o select no
// desenho da tela conforme critérios da issue, mas desabilitado até o backend
// expor GET /api/v1/projetos/.
const PROJETO_PLACEHOLDER: SelectOption[] = [
  { value: "", label: "Em breve" },
];

export function UpfsFilters({
  value,
  onChange,
  onClear,
  hasActiveFilters,
  municipioOptions,
  territorioOptions,
  optionsLoading,
}: UpfsFiltersProps) {
  const municipioSelectOptions: SelectOption[] = [
    { value: "", label: "Todos os municípios" },
    ...municipioOptions,
  ];
  const territorioSelectOptions: SelectOption[] = [
    { value: "", label: "Todos os territórios" },
    ...territorioOptions,
  ];

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4">
      {/* Linha 1: busca + status */}
      <div className="flex flex-wrap items-end gap-3">
        <Input
          id="upfs-search"
          type="search"
          label="Buscar"
          value={value.search}
          onChange={(e) => onChange({ search: e.target.value })}
          placeholder="Buscar por nome ou CPF..."
          startIcon={<Search className="h-4 w-4" />}
          className="min-w-60 flex-1"
        />

        <div className="flex w-65 shrink-0 flex-col gap-1">
          <span className={fieldLabelClass}>Status</span>
          <div
            role="group"
            aria-label="Filtrar por status"
            className="flex h-9 items-center rounded-md border border-border bg-surface p-0.5"
          >
            {STATUS_SEGMENTS.map((seg) => {
              const active = value.status === seg.value;
              return (
                <button
                  key={seg.value}
                  type="button"
                  aria-pressed={active}
                  onClick={() => onChange({ status: seg.value })}
                  className={`flex-1 rounded-sm px-3 text-xs font-medium leading-8 transition-colors ${
                    active
                      ? "bg-primary text-surface"
                      : "text-text-muted hover:text-text"
                  }`}
                >
                  {seg.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Linha 2: município + território + projeto */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-40 flex-1">
          <Select
            label="Município"
            options={municipioSelectOptions}
            value={value.municipio}
            onChange={(v) => onChange({ municipio: v })}
            disabled={optionsLoading}
            placeholder="Todos os municípios"
          />
        </div>

        <div className="min-w-40 flex-1">
          <Select
            label="Território"
            options={territorioSelectOptions}
            value={value.territorio}
            onChange={(v) => onChange({ territorio: v })}
            disabled={optionsLoading}
            placeholder="Todos os territórios"
          />
        </div>

        <div className="min-w-40 flex-1">
          <Select
            label="Projeto"
            options={PROJETO_PLACEHOLDER}
            value=""
            disabled
            placeholder="Em breve"
          />
        </div>
      </div>

      {/* Linha 3: período de cadastro + limpar */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex shrink-0 flex-col gap-1">
          <span className={fieldLabelClass}>Cadastrado em</span>
          <div className="flex items-center gap-2">
            <input
              type="date"
              aria-label="Cadastrado de"
              value={value.cadastradoDe}
              max={value.cadastradoAte || undefined}
              onChange={(e) => onChange({ cadastradoDe: e.target.value })}
              className="h-9 w-36 rounded-md border border-border bg-surface px-2 text-sm text-text outline-none transition duration-120 enabled:hover:border-text-muted focus:border-primary"
            />
            <span className="shrink-0 text-xs text-text-muted">até</span>
            <input
              type="date"
              aria-label="Cadastrado até"
              value={value.cadastradoAte}
              min={value.cadastradoDe || undefined}
              onChange={(e) => onChange({ cadastradoAte: e.target.value })}
              className="h-9 w-36 rounded-md border border-border bg-surface px-2 text-sm text-text outline-none transition duration-120 enabled:hover:border-text-muted focus:border-primary"
            />
          </div>
        </div>

        {hasActiveFilters && (
          <button
            type="button"
            onClick={onClear}
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md px-3 text-sm text-text-muted transition-colors hover:bg-surface-muted hover:text-text"
          >
            <X className="h-3.5 w-3.5" />
            Limpar filtros
          </button>
        )}
      </div>
    </div>
  );
}
