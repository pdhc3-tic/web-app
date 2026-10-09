"use client";

import { X } from "lucide-react";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import type { AcaoPT } from "@/app/lib/atividades";
import type { SgpChoices } from "@/app/lib/choices";
import { AcaoCombobox } from "../../_components/AcaoCombobox";

/**
 * Filtros aceitos pelo endpoint /atividades/calendario/ (BE-3, Issue #126).
 * Território não é filtrado por lá — a RLS já limita o escopo do usuário.
 */
export type CalendarFiltersValue = {
  acao: string;
  projeto: string;
  tecnico: string;
  tipo: string;
  status: string;
};

export const EMPTY_CALENDAR_FILTERS: CalendarFiltersValue = {
  acao: "",
  projeto: "",
  tecnico: "",
  tipo: "",
  status: "",
};

type Props = {
  value: CalendarFiltersValue;
  onChange: (patch: Partial<CalendarFiltersValue>) => void;
  onClear: () => void;
  hasActiveFilters: boolean;
  acoes: AcaoPT[];
  acaoSelecionada: AcaoPT | null;
  choices: SgpChoices;
  projetoOptions: SelectOption[];
  tecnicoOptions: SelectOption[];
  optionsLoading: boolean;
};

function withTodos(options: SelectOption[], label: string): SelectOption[] {
  return [{ value: "", label }, ...options];
}

export function CalendarFilters({
  value,
  onChange,
  onClear,
  hasActiveFilters,
  acoes,
  acaoSelecionada,
  choices,
  projetoOptions,
  tecnicoOptions,
  optionsLoading,
}: Props) {
  // Endpoint de usuários é restrito a Super Admin — igual à lista de atividades.
  const tecnicoIndisponivel = !optionsLoading && tecnicoOptions.length === 0;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-60 flex-2">
          <AcaoCombobox
            id="calendario-filtro-acao"
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

      <div className="flex flex-wrap items-end gap-3">
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

        <div className="min-w-40 flex-1">
          <Select
            label="Status"
            options={withTodos(choices.status, "Todos os status")}
            value={value.status}
            onChange={(v) => onChange({ status: v })}
            placeholder="Todos os status"
          />
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
