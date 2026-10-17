import { apiClient } from "@/app/lib/api";

export interface LinhaPainelRubrica {
  rubrica_id: number;
  rubrica_slug: string;
  rubrica_nome: string;
  solicitado: string;
  autorizado: string;
  executado: string;
  disponivel: string;
}

export interface AtividadeCusto {
  atividade_id: number;
  atividade_titulo: string;
  demandas: number;
  estimado: string;
  autorizado: string;
  pago: string;
}

export interface EntregaCusto {
  acao_id: number;
  acao_numero: string;
  acao_descricao: string;
  demandas: number;
  estimado: string;
  autorizado: string;
  pago: string;
  atividades: AtividadeCusto[];
}

export interface ExecucaoFiltros {
  status?: string;
  tipo?: string;
  rubrica?: string;
  solicitante?: string;
  atividade?: string;
  acao?: string;
  submeta?: string;
  meta?: string;
  territorio?: string;
  estado?: string;
  periodo_inicio?: string;
  periodo_fim?: string;
  responsavel_etapa_atual?: string;
}

export type SemaforoRubricaNivel = "verde" | "amarelo" | "vermelho" | "sem-dado";

/**
 * Calcula o semáforo 70/90 para a execução da rubrica (RF28 / Issue #297).
 * - Acima de 90%: "vermelho"
 * - Entre 70% e 90%: "amarelo" (destaque terracota do SGD #B05A2F)
 * - Abaixo de 70%: "verde"
 * - Sem orçamento disponível/executado: "sem-dado"
 */
export function calcularSemaforoRubrica(linha: LinhaPainelRubrica): {
  nivel: SemaforoRubricaNivel;
  percentual: number | null;
} {
  const executado = Number(linha.executado || 0);
  const disponivel = Number(linha.disponivel || 0);
  const total = executado + disponivel;

  if (total <= 0) {
    return { nivel: "sem-dado", percentual: null };
  }

  const percentual = (executado / total) * 100;

  if (percentual >= 90) return { nivel: "vermelho", percentual };
  if (percentual >= 70) return { nivel: "amarelo", percentual };
  return { nivel: "verde", percentual };
}

/**
 * Consulta o painel de execução por rubrica (GET /api/v1/sgd/painel/rubricas/).
 */
export async function fetchPainelRubricas(
  params?: Pick<ExecucaoFiltros, "territorio" | "meta" | "estado">,
  signal?: AbortSignal,
): Promise<LinhaPainelRubrica[]> {
  const qs = new URLSearchParams();
  if (params?.territorio) qs.set("territorio", params.territorio);
  if (params?.meta) qs.set("meta", params.meta);
  if (params?.estado) qs.set("estado", params.estado);

  const queryStr = qs.toString();
  const url = `/api/v1/sgd/painel/rubricas/${queryStr ? `?${queryStr}` : ""}`;
  const res = await apiClient(url, { signal });
  return res.json();
}

/**
 * Consulta o relatório de custo por atividade e entrega (GET /api/v1/sgd/relatorios/custo-por-atividade/).
 */
export async function fetchCustoPorAtividade(
  filtros?: ExecucaoFiltros,
  signal?: AbortSignal,
): Promise<EntregaCusto[]> {
  const qs = new URLSearchParams();
  if (filtros) {
    for (const [k, v] of Object.entries(filtros)) {
      if (v) qs.set(k, v);
    }
  }

  const queryStr = qs.toString();
  const url = `/api/v1/sgd/relatorios/custo-por-atividade/${queryStr ? `?${queryStr}` : ""}`;
  const res = await apiClient(url, { signal });
  return res.json();
}

function dispararDownload(blob: Blob, nome: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function extrairNomeArquivo(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const match = header.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  return match && match[1] ? decodeURIComponent(match[1]) : fallback;
}

/**
 * Exporta as demandas filtradas em CSV ou XLSX (GET /api/v1/sgd/demandas/exportar/).
 */
export async function baixarExportacaoDemandas(
  filtros: ExecucaoFiltros & { formato: "csv" | "xlsx" },
): Promise<string> {
  const { formato, ...resto } = filtros;
  const qs = new URLSearchParams({ formato });

  for (const [k, v] of Object.entries(resto)) {
    if (v) qs.set(k, v);
  }

  const res = await apiClient(`/api/v1/sgd/demandas/exportar/?${qs}`);
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition");
  const fallbackNome = `demandas_${new Date().toISOString().slice(0, 10)}.${formato}`;
  const nomeFinal = extrairNomeArquivo(disposition, fallbackNome);

  dispararDownload(blob, nomeFinal);
  return nomeFinal;
}
