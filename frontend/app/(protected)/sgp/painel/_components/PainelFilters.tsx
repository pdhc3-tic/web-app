"use client";

import { X } from "lucide-react";
import { Select } from "@/app/components/ui/Select/Select";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { acaoStatusLabel } from "@/app/lib/acoes";

export type PainelFiltersValue = {
  /** Id da Meta, como string (valor do <Select>). "" = todas. */
  meta: string;
  /** Id do território. "" = todos. */
  territorio: string;
  /** status_execucao da Ação. "" = todas as situações. */
  situacao: string;
};

export const FILTROS_VAZIOS: PainelFiltersValue = {
  meta: "",
  territorio: "",
  situacao: "",
};

/**
 * Os três valores que o backend aceita em `status_execucao`
 * (WorkPlanDashboardQuerySerializer). Exportados porque a página também os usa
 * para sanear o que vem da URL.
 */
export const SITUACOES_VALIDAS = ["no_prazo", "em_atraso", "concluida"];

/** Rótulos vêm de `acaoStatusLabel` para não abrir um segundo mapa. */
const SITUACAO_OPTIONS: SelectOption[] = SITUACOES_VALIDAS.map((value) => ({
  value,
  label: acaoStatusLabel(value),
}));

type Props = {
  value: PainelFiltersValue;
  onChange: (patch: Partial<PainelFiltersValue>) => void;
  onClear: () => void;
  metaOptions: SelectOption[];
  territorioOptions: SelectOption[];
  optionsLoading: boolean;
};

export function PainelFilters({
  value,
  onChange,
  onClear,
  metaOptions,
  territorioOptions,
  optionsLoading,
}: Props) {
  const temFiltro =
    value.meta !== "" || value.territorio !== "" || value.situacao !== "";

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

        <div className="min-w-40 flex-1">
          <Select
            id="painel-filtro-situacao"
            label="Situação"
            options={[
              { value: "", label: "Todas as situações" },
              ...SITUACAO_OPTIONS,
            ]}
            value={value.situacao}
            onChange={(v) => onChange({ situacao: v })}
            placeholder="Todas as situações"
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
          className="text-xs leading-relaxed text-text-muted"
          data-testid="painel-aviso-territorio"
        >
          Exibindo apenas Ações com Atividades de Campo neste território. O
          semáforo continua medindo a execução total da Ação — não há
          planejamento por território.
        </p>
      )}
    </div>
  );
}
