"use client";

import { useEffect, useState } from "react";
import { Filter, X } from "lucide-react";
import { Select } from "@/app/components/ui/Select/Select";
import { apiClient } from "@/app/lib/api";
import type { ExecucaoFiltros } from "@/app/lib/execucaoSgd";
import { listMetas, type MetaListItem } from "@/app/lib/metas";

const STATUS_OPTIONS = [
  { value: "", label: "Todos os status" },
  { value: "submetida", label: "Submetida" },
  { value: "pre_autorizada", label: "Pré-autorizada" },
  { value: "autorizada", label: "Autorizada" },
  { value: "em_atendimento", label: "Em atendimento" },
  { value: "concluida", label: "Concluída" },
  { value: "recusada", label: "Recusada" },
  { value: "cancelada", label: "Cancelada" },
  { value: "devolvida", label: "Devolvida" },
];

/**
 * Tipo das solicitações. Os `value` espelham `TIPO_CHOICES` em
 * `apps/sgd/models/demand_request.py` — valor errado leva o backend a 400 e
 * nenhum resultado chegaria à tela.
 */
const TIPO_OPTIONS = [
  { value: "", label: "Todos os tipos" },
  { value: "diaria", label: "Diárias" },
  { value: "passagem", label: "Passagens Aéreas" },
  { value: "veiculo", label: "Locação de Veículo" },
  { value: "grafico", label: "Material Gráfico" },
  { value: "alimentacao", label: "Alimentação" },
  { value: "equipamento", label: "Aquisição de Equipamentos" },
];

/**
 * Slugs das 6 rubricas cadastradas por `apps/sgp/migrations/0002_seed_dados_iniciais.py`.
 * O `DemandFilter.rubrica` casa pelo `slug` da `BudgetRubrica`; um valor fora
 * desta lista nunca seleciona demanda alguma.
 */
const RUBRICA_OPTIONS = [
  { value: "", label: "Todas as rubricas" },
  { value: "diarias", label: "Diárias" },
  { value: "passagens-aereas", label: "Passagens Aéreas" },
  { value: "locacao-veiculo", label: "Locação de Veículo" },
  { value: "alimentacao-refeicoes", label: "Alimentação/Refeições" },
  { value: "material-grafico", label: "Material Gráfico" },
  { value: "equipamentos-capital", label: "Equipamentos/Capital" },
];

type TerritorioItem = { id: number; nome: string };

/** Classe compartilhada com os inputs de período para manter o visual. */
const INPUT_CLASS =
  "h-9 w-full rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus:border-primary";

/** Normaliza o id digitado — vazio volta a `undefined`, para o filtro sair da query. */
function soIdOuVazio(valor: string): string | undefined {
  const limpo = valor.replace(/[^\d]/g, "");
  return limpo || undefined;
}

export function ExecucaoFilters({
  filtros,
  onChange,
}: {
  filtros: ExecucaoFiltros;
  onChange: (novo: ExecucaoFiltros) => void;
}) {
  const [territorios, setTerritorios] = useState<TerritorioItem[]>([]);
  const [metas, setMetas] = useState<MetaListItem[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    apiClient("/api/v1/territorios/", { signal: controller.signal })
      .then((res) => res.json())
      .then((data) => {
        const list = Array.isArray(data) ? data : data.results ?? [];
        setTerritorios(list);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    listMetas(controller.signal)
      .then(setMetas)
      .catch(() => {});
    return () => controller.abort();
  }, []);

  const territorioOptions = [
    { value: "", label: "Todos os territórios" },
    ...territorios.map((t) => ({ value: String(t.id), label: t.nome })),
  ];

  const metaOptions = [
    { value: "", label: "Todas as metas" },
    ...metas.map((m) => ({ value: String(m.id), label: `Meta ${m.numero}` })),
  ];

  const temFiltroAtivo = Object.values(filtros).some(Boolean);

  const limparFiltros = () => {
    onChange({});
  };

  const atualizar = (patch: Partial<ExecucaoFiltros>) => onChange({ ...filtros, ...patch });

  return (
    <div
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4 shadow-xs"
      data-testid="execucao-filtros"
    >
      <div className="flex items-center justify-between gap-2 text-xs font-semibold uppercase tracking-wider text-text-muted">
        <span className="flex items-center gap-1.5">
          <Filter className="h-3.5 w-3.5" />
          Filtros de Execução e Custo
        </span>
        {temFiltroAtivo && (
          <button
            type="button"
            onClick={limparFiltros}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            data-testid="limpar-filtros-btn"
          >
            <X className="h-3 w-3" />
            Limpar filtros
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
        <Select
          label="Status"
          value={filtros.status ?? ""}
          onChange={(v) => atualizar({ status: v || undefined })}
          options={STATUS_OPTIONS}
          name="status"
        />

        <Select
          label="Tipo"
          value={filtros.tipo ?? ""}
          onChange={(v) => atualizar({ tipo: v || undefined })}
          options={TIPO_OPTIONS}
          name="tipo"
        />

        <Select
          label="Rubrica"
          value={filtros.rubrica ?? ""}
          onChange={(v) => atualizar({ rubrica: v || undefined })}
          options={RUBRICA_OPTIONS}
          name="rubrica"
        />

        <Select
          label="Território"
          value={filtros.territorio ?? ""}
          onChange={(v) => atualizar({ territorio: v || undefined })}
          options={territorioOptions}
          name="territorio"
        />

        <div className="flex flex-col gap-1">
          <span className="text-label font-medium text-text">Período</span>
          <div className="grid grid-cols-2 gap-1.5">
            <input
              type="date"
              aria-label="Data inicial"
              value={filtros.periodo_inicio ?? ""}
              onChange={(e) => atualizar({ periodo_inicio: e.target.value || undefined })}
              className={INPUT_CLASS}
            />
            <input
              type="date"
              aria-label="Data final"
              value={filtros.periodo_fim ?? ""}
              onChange={(e) => atualizar({ periodo_fim: e.target.value || undefined })}
              className={INPUT_CLASS}
            />
          </div>
        </div>
      </div>

      {/* Filtros de granularidade fina do DemandFilter (BE-5): o DRF casa por id
          numérico; não há endpoint aberto para listar solicitantes/atividades no
          escopo dos perfis que não são Super Admin, então vai como id até o
          backend expor um combobox próprio. */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
        <Select
          label="Meta"
          value={filtros.meta ?? ""}
          onChange={(v) => atualizar({ meta: v || undefined })}
          options={metaOptions}
          name="meta"
        />

        <div className="flex flex-col gap-1">
          <label htmlFor="filtro-submeta" className="text-label font-medium text-text">
            Submeta (ID)
          </label>
          <input
            id="filtro-submeta"
            type="number"
            min={1}
            inputMode="numeric"
            placeholder="Ex.: 12"
            value={filtros.submeta ?? ""}
            onChange={(e) => atualizar({ submeta: soIdOuVazio(e.target.value) })}
            className={INPUT_CLASS}
            data-testid="filtro-submeta"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="filtro-acao" className="text-label font-medium text-text">
            Ação (ID)
          </label>
          <input
            id="filtro-acao"
            type="number"
            min={1}
            inputMode="numeric"
            placeholder="Ex.: 34"
            value={filtros.acao ?? ""}
            onChange={(e) => atualizar({ acao: soIdOuVazio(e.target.value) })}
            className={INPUT_CLASS}
            data-testid="filtro-acao"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="filtro-atividade" className="text-label font-medium text-text">
            Atividade (ID)
          </label>
          <input
            id="filtro-atividade"
            type="number"
            min={1}
            inputMode="numeric"
            placeholder="Ex.: 128"
            value={filtros.atividade ?? ""}
            onChange={(e) => atualizar({ atividade: soIdOuVazio(e.target.value) })}
            className={INPUT_CLASS}
            data-testid="filtro-atividade"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="filtro-solicitante" className="text-label font-medium text-text">
            Solicitante (ID)
          </label>
          <input
            id="filtro-solicitante"
            type="number"
            min={1}
            inputMode="numeric"
            placeholder="Ex.: 42"
            value={filtros.solicitante ?? ""}
            onChange={(e) => atualizar({ solicitante: soIdOuVazio(e.target.value) })}
            className={INPUT_CLASS}
            data-testid="filtro-solicitante"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="filtro-responsavel" className="text-label font-medium text-text">
            Responsável etapa (ID)
          </label>
          <input
            id="filtro-responsavel"
            type="number"
            min={1}
            inputMode="numeric"
            placeholder="Ex.: 7"
            value={filtros.responsavel_etapa_atual ?? ""}
            onChange={(e) =>
              atualizar({ responsavel_etapa_atual: soIdOuVazio(e.target.value) })
            }
            className={INPUT_CLASS}
            data-testid="filtro-responsavel-etapa"
          />
        </div>
      </div>
    </div>
  );
}
