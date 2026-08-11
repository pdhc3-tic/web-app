"use client";

import { X } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Select } from "@/app/components/ui/Select/Select";
import type { SelectOption } from "@/app/components/ui/Select/Select";

export type PainelFiltersValue = {
  /** Id da Meta, como string (valor do <Select>). "" = todas. */
  meta: string;
  /** Id do território. "" = todos. */
  territorio: string;
};

export const FILTROS_VAZIOS: PainelFiltersValue = { meta: "", territorio: "" };

type Props = {
  value: PainelFiltersValue;
  onChange: (patch: Partial<PainelFiltersValue>) => void;
  onClear: () => void;
  metaOptions: SelectOption[];
  territorioOptions: SelectOption[];
  optionsLoading: boolean;
  /** true enquanto o cruzamento Ação × território está sendo resolvido. */
  territorioLoading: boolean;
};

export function PainelFilters({
  value,
  onChange,
  onClear,
  metaOptions,
  territorioOptions,
  optionsLoading,
  territorioLoading,
}: Props) {
  const temFiltro = value.meta !== "" || value.territorio !== "";

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-40 flex-1">
          <Select
            id="painel-filtro-meta"
            label="Meta"
            options={[{ value: "", label: "Todas as Metas" }, ...metaOptions]}
            value={value.meta}
            onChange={(v) => onChange({ meta: v })}
            placeholder="Todas as Metas"
          />
        </div>

        <div className="min-w-40 flex-1">
          <Select
            id="painel-filtro-territorio"
            label="Território"
            options={[
              { value: "", label: "Todos os territórios" },
              ...territorioOptions,
            ]}
            value={value.territorio}
            onChange={(v) => onChange({ territorio: v })}
            disabled={optionsLoading}
            placeholder="Todos os territórios"
          />
        </div>

        {temFiltro && (
          <button
            type="button"
            onClick={onClear}
            data-testid="painel-limpar-filtros"
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md px-3 text-sm text-text-muted transition-colors hover:bg-surface-muted hover:text-text"
          >
            <X className="h-3.5 w-3.5" aria-hidden />
            Limpar filtros
          </button>
        )}
      </div>

      {/* O recorte territorial precisa ser explicado onde ele age: o número do
          semáforo NÃO muda com o filtro, e sem esse aviso a leitura natural
          seria a errada. */}
      {value.territorio !== "" && (
        <p
          className="flex items-center gap-2 text-xs leading-relaxed text-text-muted"
          data-testid="painel-aviso-territorio"
          aria-live="polite"
        >
          {territorioLoading && (
            <Spinner className="h-3.5 w-3.5 shrink-0 animate-spin" />
          )}
          <span>
            {territorioLoading
              ? "Cruzando Ações com as Atividades de Campo do território…"
              : "Exibindo apenas Ações com Atividades de Campo neste território. O semáforo continua medindo a execução total da Ação — não há planejamento por território."}
          </span>
        </p>
      )}
    </div>
  );
}
