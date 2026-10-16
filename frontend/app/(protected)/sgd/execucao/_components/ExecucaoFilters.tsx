"use client";

import { useEffect, useState } from "react";
import { Filter, X } from "lucide-react";
import { Select } from "@/app/components/ui/Select/Select";
import { apiClient } from "@/app/lib/api";
import type { ExecucaoFiltros } from "@/app/lib/execucaoSgd";

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

const TIPO_OPTIONS = [
  { value: "", label: "Todos os tipos" },
  { value: "diarias", label: "Diárias" },
  { value: "passagem", label: "Passagem" },
  { value: "veiculo", label: "Veículo" },
  { value: "material_grafico", label: "Material Gráfico" },
  { value: "alimentacao", label: "Alimentação" },
  { value: "equipamento", label: "Equipamento" },
];

const RUBRICA_OPTIONS = [
  { value: "", label: "Todas as rubricas" },
  { value: "diarias", label: "Diárias" },
  { value: "passagens", label: "Passagens" },
  { value: "combustivel", label: "Combustível" },
  { value: "hospedagem", label: "Hospedagem" },
  { value: "alimentacao", label: "Alimentação" },
  { value: "grafica", label: "Material Gráfico" },
  { value: "equipamentos", label: "Equipamentos" },
];

type TerritorioItem = { id: number; nome: string };

export function ExecucaoFilters({
  filtros,
  onChange,
}: {
  filtros: ExecucaoFiltros;
  onChange: (novo: ExecucaoFiltros) => void;
}) {
  const [territorios, setTerritorios] = useState<TerritorioItem[]>([]);

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

  const territorioOptions = [
    { value: "", label: "Todos os territórios" },
    ...territorios.map((t) => ({ value: String(t.id), label: t.nome })),
  ];

  const temFiltroAtivo = Object.values(filtros).some(Boolean);

  const limparFiltros = () => {
    onChange({});
  };

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
          onChange={(v) => onChange({ ...filtros, status: v || undefined })}
          options={STATUS_OPTIONS}
          name="status"
        />

        <Select
          label="Tipo"
          value={filtros.tipo ?? ""}
          onChange={(v) => onChange({ ...filtros, tipo: v || undefined })}
          options={TIPO_OPTIONS}
          name="tipo"
        />

        <Select
          label="Rubrica"
          value={filtros.rubrica ?? ""}
          onChange={(v) => onChange({ ...filtros, rubrica: v || undefined })}
          options={RUBRICA_OPTIONS}
          name="rubrica"
        />

        <Select
          label="Território"
          value={filtros.territorio ?? ""}
          onChange={(v) => onChange({ ...filtros, territorio: v || undefined })}
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
              onChange={(e) =>
                onChange({ ...filtros, periodo_inicio: e.target.value || undefined })
              }
              className="h-9 w-full rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus:border-primary"
            />
            <input
              type="date"
              aria-label="Data final"
              value={filtros.periodo_fim ?? ""}
              onChange={(e) =>
                onChange({ ...filtros, periodo_fim: e.target.value || undefined })
              }
              className="h-9 w-full rounded-md border border-border bg-surface px-2 text-xs text-text outline-none focus:border-primary"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
