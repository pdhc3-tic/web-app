"use client";

import { X } from "lucide-react";
import { Select } from "@/app/components/ui/Select/Select";
import type { SelectOption } from "@/app/components/ui/Select/Select";

export type OrcamentoFiltersValue = {
  /** Id da Meta, como string. Só recorta o executado (relatório), não o saldo. "" = sem recorte. */
  meta: string;
  /** SLUG da rubrica — o backend valida por slug, não por id. "" = todas. */
  rubrica: string;
  /** SIGLA do estado — idem, o backend valida por sigla. "" = sem descer. */
  estado: string;
  /** Id do território. "" = sem descer. */
  territorio: string;
};

export const FILTROS_VAZIOS: OrcamentoFiltersValue = {
  meta: "",
  rubrica: "",
  estado: "",
  territorio: "",
};

type Props = {
  value: OrcamentoFiltersValue;
  onChange: (patch: Partial<OrcamentoFiltersValue>) => void;
  onClear: () => void;
  metaOptions: SelectOption[];
  rubricaOptions: SelectOption[];
  estadoOptions: SelectOption[];
  territorioOptions: SelectOption[];
  optionsLoading: boolean;
  /**
   * ADT/ACR: esconde por completo os seletores de estado e território.
   * `resolver_nivel_painel` fixa esse perfil no próprio território e responde
   * 403 a `estado=` — oferecer o controle seria uma afordância para um erro.
   */
  soTerritorio: boolean;
};

/**
 * Filtros do Painel de Orçamento (#398, orçamento por pool).
 *
 * Os quatro campos NÃO são a mesma coisa:
 *
 * - `rubrica` recorta a matriz: menos blocos, mesmos valores.
 * - `estado` e `territorio` descem na hierarquia: com estado, o pool do
 *   estado e os dos territórios dele; com território, só o pool do território.
 * - `meta` é só relatório: a coluna Executado passa a mostrar o executado nas
 *   atividades da Meta. Aprovado, comprometido e disponível continuam os do
 *   pool, porque desde a #384 a Meta não tem saldo próprio.
 */
export function OrcamentoFilters({
  value,
  onChange,
  onClear,
  metaOptions,
  rubricaOptions,
  estadoOptions,
  territorioOptions,
  optionsLoading,
  soTerritorio,
}: Props) {
  const temFiltro =
    value.meta !== "" ||
    value.rubrica !== "" ||
    value.estado !== "" ||
    value.territorio !== "";

  const desceuNivel = value.estado !== "" || value.territorio !== "";

  return (
    <div
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
      data-testid="orcamento-filtros"
    >
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-40 flex-1">
          <Select
            id="orcamento-filtro-meta"
            label="Executado da Meta"
            options={[{ value: "", label: "Sem recorte por Meta" }, ...metaOptions]}
            value={value.meta}
            onChange={(v) => onChange({ meta: v })}
            disabled={optionsLoading}
            placeholder="Sem recorte por Meta"
          />
        </div>

        <div className="min-w-40 flex-1">
          <Select
            id="orcamento-filtro-rubrica"
            label="Rubrica"
            options={[
              { value: "", label: "Todas as rubricas" },
              ...rubricaOptions,
            ]}
            value={value.rubrica}
            onChange={(v) => onChange({ rubrica: v })}
            disabled={optionsLoading}
            placeholder="Todas as rubricas"
          />
        </div>

        {!soTerritorio && (
          <>
            <div className="min-w-40 flex-1">
              <Select
                id="orcamento-filtro-estado"
                label="Estado"
                options={[
                  { value: "", label: "Todos os estados" },
                  ...estadoOptions,
                ]}
                value={value.estado}
                onChange={(v) =>
                  // Estado e território são mutuamente exclusivos: o backend
                  // faz `territorio` vencer quando os dois vêm juntos, e deixar
                  // um valor morto no <Select> mostraria um filtro que não está
                  // agindo. Escolher um limpa o outro.
                  onChange({ estado: v, territorio: "" })
                }
                disabled={optionsLoading}
                placeholder="Todos os estados"
              />
            </div>

            <div className="min-w-40 flex-1">
              <Select
                id="orcamento-filtro-territorio"
                label="Território"
                options={[
                  { value: "", label: "Todos os territórios" },
                  ...territorioOptions,
                ]}
                value={value.territorio}
                onChange={(v) => onChange({ territorio: v, estado: "" })}
                disabled={optionsLoading}
                placeholder="Todos os territórios"
              />
            </div>
          </>
        )}

        {temFiltro && (
          <button
            type="button"
            onClick={onClear}
            data-testid="orcamento-limpar-filtros"
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md px-3 text-sm text-text-muted transition-colors hover:bg-surface-muted hover:text-text"
          >
            <X className="h-3.5 w-3.5" aria-hidden />
            Limpar filtros
          </button>
        )}
      </div>

      {desceuNivel && (
        <p
          className="text-xs leading-relaxed text-text-muted"
          data-testid="orcamento-aviso-nivel"
        >
          {value.territorio !== ""
            ? "Só o pool do território escolhido. O aprovado dele é o que recebeu do estado."
            : "O pool do estado escolhido e os dos territórios dele. O aprovado de cada um é o que recebeu do nível acima."}
        </p>
      )}

      {value.meta !== "" && (
        <p className="text-xs leading-relaxed text-text-muted" data-testid="orcamento-aviso-meta">
          A coluna Executado mostra só o executado nas atividades desta Meta. Aprovado, comprometido e disponível
          continuam os do pool: a Meta não tem saldo próprio.
        </p>
      )}

      {soTerritorio && (
        <p
          className="text-xs leading-relaxed text-text-muted"
          data-testid="orcamento-aviso-adt"
        >
          Você está vendo o orçamento do seu território. Os pools nacional e
          estadual não fazem parte do seu escopo.
        </p>
      )}
    </div>
  );
}
