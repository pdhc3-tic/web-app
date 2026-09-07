"use client";

import { X } from "lucide-react";
import { Select } from "@/app/components/ui/Select/Select";
import type { SelectOption } from "@/app/components/ui/Select/Select";

export type OrcamentoFiltersValue = {
  /** Id da Meta, como string (valor do <Select>). "" = todas. */
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
 * Filtros do Painel de Orçamento.
 *
 * Os quatro campos NÃO são a mesma coisa, e a tela separa os dois grupos de
 * propósito:
 *
 * - `meta` e `rubrica` recortam a matriz — menos linhas, mesmos valores.
 * - `estado` e `territorio` fazem DRILL-DOWN: mudam o nível que as linhas
 *   representam, e portanto mudam os próprios números. Descer para um estado
 *   não mostra "a parte estadual do total nacional": mostra as alocações
 *   estaduais, que são outra linha do banco.
 *
 * Sem esse aviso a leitura natural seria a errada — mesmo problema que o painel
 * do PT físico resolve com o seu `painel-aviso-territorio`.
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
            label="Meta"
            options={[{ value: "", label: "Todas as Metas" }, ...metaOptions]}
            value={value.meta}
            onChange={(v) => onChange({ meta: v })}
            disabled={optionsLoading}
            placeholder="Todas as Metas"
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
                  { value: "", label: "Nível nacional" },
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
                placeholder="Nível nacional"
              />
            </div>

            <div className="min-w-40 flex-1">
              <Select
                id="orcamento-filtro-territorio"
                label="Território"
                options={[
                  { value: "", label: "Sem detalhar território" },
                  ...territorioOptions,
                ]}
                value={value.territorio}
                onChange={(v) => onChange({ territorio: v, estado: "" })}
                disabled={optionsLoading}
                placeholder="Sem detalhar território"
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
          Estado e território não recortam os valores nacionais: descem um nível
          na hierarquia. Os números abaixo são das alocações{" "}
          {value.territorio !== "" ? "territoriais" : "estaduais"}, e o
          &quot;aprovado&quot; passa a ser o que esse nível recebeu do nível
          acima.
        </p>
      )}

      {soTerritorio && (
        <p
          className="text-xs leading-relaxed text-text-muted"
          data-testid="orcamento-aviso-adt"
        >
          Você está vendo o orçamento do seu território. Os níveis nacional e
          estadual não fazem parte do seu escopo.
        </p>
      )}
    </div>
  );
}
