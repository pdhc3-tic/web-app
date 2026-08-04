"use client";

import { Search, X } from "lucide-react";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import type { StatusFilter } from "@/app/lib/users";

const fieldLabelClass = "text-label font-medium text-text leading-[1.2]";

export type UsersFiltersValue = {
  search: string;
  perfil: string;
  territorio: string;
  status: StatusFilter;
  ultimoAcessoDe: string;
  ultimoAcessoAte: string;
};

type UsersFiltersProps = {
  value: UsersFiltersValue;
  onChange: (patch: Partial<UsersFiltersValue>) => void;
  onClear: () => void;
  hasActiveFilters: boolean;
  roleOptions: SelectOption[];
  territoryOptions: SelectOption[];
  optionsLoading: boolean;
};

const STATUS_SEGMENTS: { value: StatusFilter; label: string }[] = [
  { value: "ativos", label: "Ativos" },
  { value: "inativos", label: "Inativos" },
  { value: "todos", label: "Todos" },
];

export function UsersFilters({
  value,
  onChange,
  onClear,
  hasActiveFilters,
  roleOptions,
  territoryOptions,
  optionsLoading,
}: UsersFiltersProps) {
  const perfilOptions: SelectOption[] = [
    { value: "", label: "Todos os perfis" },
    ...roleOptions,
  ];
  const territorioOptions: SelectOption[] = [
    { value: "", label: "Todos os territórios" },
    ...territoryOptions,
  ];

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4">
      {/* Linha 1: busca + status */}
      <div className="flex flex-wrap items-end gap-3">
        <Input
          id="users-search"
          type="search"
          label="Buscar"
          value={value.search}
          onChange={(e) => onChange({ search: e.target.value })}
          placeholder="Buscar por nome ou e-mail..."
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

      {/* Linha 2: perfil + território + último acesso + limpar */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-40 flex-1">
          <Select
            label="Perfil"
            options={perfilOptions}
            value={value.perfil}
            onChange={(v) => onChange({ perfil: v })}
            disabled={optionsLoading}
            placeholder="Todos os perfis"
          />
        </div>

        <div className="min-w-40 flex-1">
          <Select
            label="Território"
            options={territorioOptions}
            value={value.territorio}
            onChange={(v) => onChange({ territorio: v })}
            disabled={optionsLoading}
            placeholder="Todos os territórios"
          />
        </div>

        <div className="flex shrink-0 flex-col gap-1">
          <span className={fieldLabelClass}>Último acesso</span>
          <div className="flex items-center gap-2">
            <input
              type="date"
              aria-label="Último acesso de"
              value={value.ultimoAcessoDe}
              max={value.ultimoAcessoAte || undefined}
              onChange={(e) => onChange({ ultimoAcessoDe: e.target.value })}
              className="h-9 w-36 rounded-md border border-border bg-surface px-2 text-sm text-text outline-none transition duration-120 enabled:hover:border-text-muted focus:border-primary"
            />
            <span className="shrink-0 text-xs text-text-muted">até</span>
            <input
              type="date"
              aria-label="Último acesso até"
              value={value.ultimoAcessoAte}
              min={value.ultimoAcessoDe || undefined}
              onChange={(e) => onChange({ ultimoAcessoAte: e.target.value })}
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
