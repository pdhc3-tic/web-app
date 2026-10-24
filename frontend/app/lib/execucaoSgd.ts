import type { SelectOption } from "@/app/components/ui/Select/Select";
import { apiClient } from "@/app/lib/api";

/**
 * `PainelRubricaSerializer`. `percentual_execucao` e `faixa` são os do controle
 * financeiro do SGP (comprometido sobre o aprovado, com os limiares do
 * `SystemConfig`) — o front só exibe, não recalcula.
 */
export interface LinhaPainelRubrica {
  rubrica_id: number;
  rubrica_slug: string;
  rubrica_nome: string;
  solicitado: string;
  autorizado: string;
  executado: string;
  disponivel: string;
  percentual_execucao: string;
  faixa: FaixaSemaforo;
}

export type FaixaSemaforo = "verde" | "amarelo" | "vermelho";

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

/** Filtros do `DemandFilter` (BE-5) que a tela de execução oferece. */
export const CHAVES_FILTRO = [
  "status",
  "tipo",
  "rubrica",
  "solicitante",
  "atividade",
  "acao",
  "submeta",
  "meta",
  "territorio",
  "periodo_inicio",
  "periodo_fim",
  "responsavel_etapa_atual",
] as const;

export type ChaveFiltro = (typeof CHAVES_FILTRO)[number];
export type ExecucaoFiltros = Partial<Record<ChaveFiltro, string>>;

/** Lê os filtros da URL — a tela guarda o recorte lá para sobreviver ao "voltar". */
export function filtrosDaUrl(params: URLSearchParams): ExecucaoFiltros {
  const filtros: ExecucaoFiltros = {};
  for (const chave of CHAVES_FILTRO) {
    const valor = params.get(chave);
    if (valor) filtros[chave] = valor;
  }
  return filtros;
}

/** Query string só com os filtros preenchidos. */
export function queryDeFiltros(filtros: ExecucaoFiltros): URLSearchParams {
  const qs = new URLSearchParams();
  for (const chave of CHAVES_FILTRO) {
    const valor = filtros[chave];
    if (valor) qs.set(chave, valor);
  }
  return qs;
}

function comQuery(path: string, filtros: ExecucaoFiltros): string {
  const qs = queryDeFiltros(filtros).toString();
  return qs ? `${path}?${qs}` : path;
}

/** GET /api/v1/sgd/painel/rubricas/ — o `DemandFilter` inteiro recorta o painel. */
export async function fetchPainelRubricas(
  filtros: ExecucaoFiltros,
  signal?: AbortSignal,
): Promise<LinhaPainelRubrica[]> {
  const res = await apiClient(comQuery("/api/v1/sgd/painel/rubricas/", filtros), { signal });
  return res.json();
}

/** GET /api/v1/sgd/relatorios/custo-por-atividade/ — agrupado pela entrega (Ação). */
export async function fetchCustoPorAtividade(
  filtros: ExecucaoFiltros,
  signal?: AbortSignal,
): Promise<EntregaCusto[]> {
  const res = await apiClient(
    comQuery("/api/v1/sgd/relatorios/custo-por-atividade/", filtros),
    { signal },
  );
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
 * GET /api/v1/sgd/demandas/exportar/ — as demandas com os filtros ativos.
 *
 * O nome vem do `Content-Disposition`; enquanto o backend não o expõe no CORS
 * (docs/pendencias-backend-sprint-10.md, item 25), o navegador o esconde e
 * vale o nome padrão.
 */
export async function baixarExportacaoDemandas(
  filtros: ExecucaoFiltros,
  formato: "csv" | "xlsx",
): Promise<string> {
  const qs = queryDeFiltros(filtros);
  qs.set("formato", formato);
  const res = await apiClient(`/api/v1/sgd/demandas/exportar/?${qs}`);
  const blob = await res.blob();
  const fallbackNome = `demandas_${new Date().toISOString().slice(0, 10)}.${formato}`;
  const nomeFinal = extrairNomeArquivo(res.headers.get("Content-Disposition"), fallbackNome);

  dispararDownload(blob, nomeFinal);
  return nomeFinal;
}

/** Percentual no formato brasileiro ("95,0%"). */
export function formatPercentual(valor: string | number): string {
  const n = Number(valor);
  if (!Number.isFinite(n)) return "—";
  return `${n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

// ─── Opções dos filtros ─────────────────────────────────────────────────────

type Paginated<T> = { results: T[] };

/** GET /api/v1/sgp/submetas/ — leitura aberta a qualquer perfil autenticado. */
export async function fetchSubmetaOptions(signal?: AbortSignal): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/sgp/submetas/?page_size=200", { signal });
  const data: Paginated<{ id: number; numero: string; titulo: string }> = await res.json();
  return data.results
    .map((s) => ({ value: String(s.id), label: `${s.numero} — ${s.titulo}` }))
    .sort((a, b) => a.label.localeCompare(b.label, "pt-BR", { numeric: true }));
}

export type PapelUsuario = "solicitante" | "responsavel";

/**
 * GET /api/v1/sgd/opcoes/usuarios/?papel= — solicitantes ou responsáveis de
 * etapa no escopo do perfil, `[{id, nome}]`. Contrato pedido ao backend na
 * pendência 26 — a tela já consome a rota e passa a listar quando ela existir.
 */
export async function fetchOpcoesUsuarios(
  papel: PapelUsuario,
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient(`/api/v1/sgd/opcoes/usuarios/?papel=${papel}`, { signal });
  const data: { id: number; nome: string }[] = await res.json();
  return data.map((u) => ({ value: String(u.id), label: u.nome }));
}

export type AtividadeOpcao = { id: number; titulo: string };

/** GET /api/v1/sgp/atividades/?q= — busca da atividade para o filtro. */
export async function buscarAtividadesParaFiltro(
  texto: string,
  signal?: AbortSignal,
): Promise<AtividadeOpcao[]> {
  const qs = new URLSearchParams({ page_size: "20", ordering: "-data_inicio" });
  if (texto.trim()) qs.set("q", texto.trim());
  const res = await apiClient(`/api/v1/sgp/atividades/?${qs}`, { signal });
  const data: Paginated<AtividadeOpcao> = await res.json();
  return data.results;
}
