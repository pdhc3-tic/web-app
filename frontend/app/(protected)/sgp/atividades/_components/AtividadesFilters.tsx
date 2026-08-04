"use client";

import { X } from "lucide-react";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import type { AcaoPT, AtividadeChoices } from "@/app/lib/atividades";
import { AcaoCombobox } from "./AcaoCombobox";

const fieldLabelClass = "text-label font-medium text-text leading-[1.2]";

export type AtividadesFiltersValue = {
  acao: string;
  projeto: string;
  territorio: string;
  tecnico: string;
  tipo: string;
  status: string;
  inicioDe: string;
  inicioAte: string;
};

export const EMPTY_FILTERS: AtividadesFiltersValue = {
  acao: "",
  projeto: "",
  territorio: "",
  tecnico: "",
  tipo: "",
  status: "",
  inicioDe: "",
  inicioAte: "",
};

type Props = {
  value: AtividadesFiltersValue;
  onChange: (patch: Partial<AtividadesFiltersValue>) => void;
  onClear: () => void;
  hasActiveFilters: boolean;
  /** Lista completa de ações; o combobox filtra em memória. */
  acoes: AcaoPT[];
  /** Ação correspondente a `value.acao`, resolvida pela página. */
  acaoSelecionada: AcaoPT | null;
  /** Choices vindos de /api/v1/choices/ (com fallback local). */
  choices: AtividadeChoices;
  projetoOptions: SelectOption[];
  territorioOptions: SelectOption[];
  tecnicoOptions: SelectOption[];
  optionsLoading: boolean;
};

function withTodos(options: SelectOption[], label: string): SelectOption[] {
  return [{ value: "", label }, ...options];
}

export function AtividadesFilters({
  value,
  onChange,
  onClear,
  hasActiveFilters,
  acoes,
  acaoSelecionada,
  choices,
  projetoOptions,
  territorioOptions,
  tecnicoOptions,
  optionsLoading,
}: Props) {
  // O endpoint de usuários é restrito a Super Admin: sem opções, o filtro de
  // técnico não tem como funcionar. Mesmo tratamento do formulário.
  const tecnicoIndisponivel = !optionsLoading && tecnicoOptions.length === 0;

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4">
      {/* Linha 1: ação do PT + projeto */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-60 flex-2">
          <AcaoCombobox
            id="atividades-filtro-acao"
            acoes={acoes}
            value={acaoSelecionada}
            onChange={(acao) => onChange({ acao: acao ? String(acao.id) : "" })}
            loading={optionsLoading}
          />
        </div>

        <div className="min-w-40 flex-1">
          <Select
            label="Projeto"
            options={withTodos(projetoOptions, "Todos os projetos")}
            value={value.projeto}
            onChange={(v) => onChange({ projeto: v })}
            disabled={optionsLoading}
            placeholder="Todos os projetos"
          />
        </div>
      </div>

      {/* Linha 2: território + técnico + tipo */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-40 flex-1">
          <Select
            label="Território"
            options={withTodos(territorioOptions, "Todos os territórios")}
            value={value.territorio}
            onChange={(v) => onChange({ territorio: v })}
            disabled={optionsLoading}
            placeholder="Todos os territórios"
          />
        </div>

        <div className="min-w-40 flex-1">
          <Select
            label="Técnico"
            options={withTodos(tecnicoOptions, "Todos os técnicos")}
            value={value.tecnico}
            onChange={(v) => onChange({ tecnico: v })}
            disabled={optionsLoading || tecnicoIndisponivel}
            placeholder={
              tecnicoIndisponivel
                ? "Indisponível para o seu perfil"
                : "Todos os técnicos"
            }
            helperText={
              tecnicoIndisponivel
                ? "A listagem de usuários é restrita no backend."
                : undefined
            }
          />
        </div>

        <div className="min-w-40 flex-1">
          <Select
            label="Tipo de atividade"
            options={withTodos(choices.tipo_atividade, "Todos os tipos")}
            value={value.tipo}
            onChange={(v) => onChange({ tipo: v })}
            placeholder="Todos os tipos"
          />
        </div>
      </div>

      {/* Linha 3: status + período de início + limpar */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-40 flex-1">
          <Select
            label="Status"
            options={withTodos(choices.status, "Todos os status")}
            value={value.status}
            onChange={(v) => onChange({ status: v })}
            placeholder="Todos os status"
          />
        </div>

        <div className="flex shrink-0 flex-col gap-1">
          {/* "Início entre" e não "Período": o ActivityFilter só filtra
              data_inicio — não há filtro sobre data_fim no backend. */}
          <span className={fieldLabelClass}>Início entre</span>
          <div className="flex items-center gap-2">
            <input
              type="date"
              aria-label="Início a partir de"
              value={value.inicioDe}
              max={value.inicioAte || undefined}
              onChange={(e) => onChange({ inicioDe: e.target.value })}
              className="h-9 w-36 rounded-md border border-border bg-surface px-2 text-sm text-text outline-none transition duration-120 enabled:hover:border-text-muted focus:border-primary"
            />
            <span className="shrink-0 text-xs text-text-muted">até</span>
            <input
              type="date"
              aria-label="Início até"
              value={value.inicioAte}
              min={value.inicioDe || undefined}
              onChange={(e) => onChange({ inicioAte: e.target.value })}
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
