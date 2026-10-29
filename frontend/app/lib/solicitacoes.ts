import { apiClient, ApiError } from "@/app/lib/api";
import { uploadToStorage } from "@/app/components/sgp/PhotoUploader/photoUpload";
import type { SearchSelectOption } from "@/app/components/ui/SearchSelect/SearchSelect";
import type { TipoSolicitacao } from "@/app/lib/camposSolicitacao";
import type { Demanda, FaixaSemaforo, SolicitacaoDemanda } from "@/app/lib/demandas";
import type { Paginated } from "@/app/lib/users";

/**
 * SGD — montar e submeter a demanda (#295): solicitações de recurso, saldo
 * antes da submissão, simulação de diárias e documentos.
 *
 * Tipos escritos à mão, como em `demandas.ts`: o `DemandViewSet` é um
 * `ViewSet` sem serializer declarado no schema (pendências, itens 5 e 6).
 */

const DEMANDAS_PATH = "/api/v1/sgd/demandas/";

/** `STATUS_EDITAVEIS` de `apps/sgd/models/demand.py`: só nesses o solicitante mexe. */
export const STATUS_DEMANDA_EDITAVEIS = ["rascunho", "devolvida"];

export function podeMontarDemanda(demanda: Demanda, usuarioId: string | number | undefined): boolean {
  return (
    String(demanda.solicitante) === String(usuarioId) && STATUS_DEMANDA_EDITAVEIS.includes(demanda.status)
  );
}

// ─── Solicitações ────────────────────────────────────────────────────────────

export type SolicitacaoPayload = {
  tipo: TipoSolicitacao;
  campos_json: Record<string, unknown>;
  /** Decimal "1234.56". Fica de fora na diária, que o backend calcula. */
  valor_estimado?: string;
};

/** POST /sgd/demandas/{id}/solicitacoes/ */
export async function criarSolicitacao(
  demandaId: number,
  payload: SolicitacaoPayload,
): Promise<SolicitacaoDemanda> {
  const res = await apiClient(`${DEMANDAS_PATH}${demandaId}/solicitacoes/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** PATCH /sgd/demandas/{id}/solicitacoes/{sid}/ */
export async function atualizarSolicitacao(
  demandaId: number,
  solicitacaoId: number,
  payload: SolicitacaoPayload,
): Promise<SolicitacaoDemanda> {
  const res = await apiClient(`${DEMANDAS_PATH}${demandaId}/solicitacoes/${solicitacaoId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/** DELETE /sgd/demandas/{id}/solicitacoes/{sid}/ — em Devolvida, libera a reserva. */
export async function removerSolicitacao(demandaId: number, solicitacaoId: number): Promise<void> {
  await apiClient(`${DEMANDAS_PATH}${demandaId}/solicitacoes/${solicitacaoId}/`, { method: "DELETE" });
}

/** POST /sgd/demandas/{id}/submeter/ — tudo ou nada: reserva as duas travas de todas. */
export async function submeterDemanda(demandaId: number): Promise<Demanda> {
  const res = await apiClient(`${DEMANDAS_PATH}${demandaId}/submeter/`, { method: "POST" });
  return res.json();
}

// ─── Bloqueio na submissão ───────────────────────────────────────────────────

/** Um item de `solicitacoes_bloqueadas` (`balance.bloqueio`). */
export type BloqueioSolicitacao = {
  trava: "individual" | "territorial";
  motivo: string | null;
  acao_sugerida: "solicitar_recurso_extra" | "acionar_articulador";
};

/**
 * Lê o 400 de `submeter/` barrado por saldo: {id da solicitação: bloqueio}.
 * Null quando o 400 é outro (sem solicitações, cotações faltando…).
 *
 * Lê o contrato atual (`solicitacoes_bloqueadas` com o motivo em texto); a
 * SGD-REF-FE-01 (#359) troca pelo `INSUFFICIENT_BALANCE` quando o backend
 * publicar a #349.
 */
export function bloqueiosDaSubmissao(erro: unknown): Record<number, BloqueioSolicitacao> | null {
  if (!(erro instanceof ApiError) || erro.status !== 400) return null;
  const raw = erro.raw as { solicitacoes_bloqueadas?: Record<string, BloqueioSolicitacao> } | undefined;
  const bloqueadas = raw?.solicitacoes_bloqueadas;
  if (!bloqueadas || typeof bloqueadas !== "object") return null;
  const porId: Record<number, BloqueioSolicitacao> = {};
  for (const [id, bloqueio] of Object.entries(bloqueadas)) porId[Number(id)] = bloqueio;
  return Object.keys(porId).length > 0 ? porId : null;
}

// ─── Saldo (BE-2) ────────────────────────────────────────────────────────────

export type TravaSaldo = {
  disponivel: boolean;
  saldo: string;
  motivo_bloqueio: string | null;
  acao_sugerida: string | null;
  semaforo_atual: FaixaSemaforo | null;
  semaforo_apos: FaixaSemaforo | null;
};

/** `SaldoConsultaSerializer` (`apps/sgd/serializers/saldo.py`). */
export type SaldoConsulta = {
  rubrica_slug: string;
  rubrica_nome: string;
  individual: TravaSaldo;
  territorial: TravaSaldo;
  disponivel: boolean;
  trava_bloqueada: "individual" | "territorial" | null;
};

/**
 * GET /api/v1/sgd/saldo/?activity_id=&tipo=&valor= — as duas travas do
 * solicitante logado para o valor informado, na rubrica que o mapeamento
 * tipo → rubrica dá ao tipo.
 */
export async function consultarSaldo(
  params: { atividadeId: number; tipo: TipoSolicitacao; valor: string },
  signal?: AbortSignal,
): Promise<SaldoConsulta> {
  const qs = new URLSearchParams({
    activity_id: String(params.atividadeId),
    tipo: params.tipo,
    valor: params.valor,
  });
  const res = await apiClient(`/api/v1/sgd/saldo/?${qs}`, { signal });
  return res.json();
}

// ─── Simulação de diárias (pendência 27) ─────────────────────────────────────

/** Contrato pedido ao backend na pendência 27, com os nomes da SGD-REF-BE-12 (#358). */
export type SimulacaoDiarias = {
  faixa_destino: { id: number; nome: string };
  valor_por_diaria: string;
  /** Decimal: com meia diária, "2.5". */
  numero_diarias: string;
  valor_total: string;
};

/**
 * GET /api/v1/sgd/config/diarias/simular/?municipio_destino_id=&data_inicio=&data_fim=
 *
 * Rota da SGD-REF-BE-12 (#358), pedida na pendência 27: o solicitante não lê o
 * valor da diária (`SystemConfig` é só do Super Admin e da UGP), então o total
 * em tempo real depende dela. Enquanto não existe, a pré-visualização mostra o
 * erro, e o total aparece ao salvar — calculado pelo backend.
 */
export async function simularDiarias(
  params: { municipioDestinoId: string; dataInicio: string; dataFim: string },
  signal?: AbortSignal,
): Promise<SimulacaoDiarias> {
  const qs = new URLSearchParams({
    municipio_destino_id: params.municipioDestinoId,
    data_inicio: params.dataInicio,
    data_fim: params.dataFim,
  });
  const res = await apiClient(`/api/v1/sgd/config/diarias/simular/?${qs}`, { signal });
  return res.json();
}

// ─── Municípios de destino ───────────────────────────────────────────────────

type MunicipioApi = { id: number; nome: string };

/** GET /api/v1/municipalities/?search= — busca de município pelo nome. */
export async function buscarMunicipios(
  texto: string,
  signal?: AbortSignal,
): Promise<SearchSelectOption<MunicipioApi>[]> {
  const qs = new URLSearchParams({ limit: "20" });
  if (texto.trim()) qs.set("search", texto.trim());
  const res = await apiClient(`/api/v1/municipalities/?${qs}`, { signal });
  const data: Paginated<MunicipioApi> = await res.json();
  return data.results.map((m) => ({ value: String(m.id), label: m.nome, item: m }));
}

/** GET /api/v1/municipalities/{id}/ — o nome do destino de uma diária salva. */
export async function getMunicipio(id: string, signal?: AbortSignal): Promise<MunicipioApi> {
  const res = await apiClient(`/api/v1/municipalities/${id}/`, { signal });
  return res.json();
}

// ─── Documentos ──────────────────────────────────────────────────────────────

/** Espelha `views/demand_document.py`: só PDF, até 10 MB, até 10 por demanda. */
export const DOCUMENTO_CONTENT_TYPE = "application/pdf";
export const DOCUMENTO_MAX_BYTES = 10_485_760;
export const DOCUMENTOS_POR_DEMANDA = 10;

/** `DemandDocumentSerializer`. */
export type DocumentoDemanda = {
  id: number;
  demanda: number;
  tipo: string;
  tipo_display: string;
  arquivo_url: string;
  descricao: string;
  fornecedor: string;
  nome_original: string;
  content_type: string;
  tamanho_bytes: number;
  enviado_por: number;
  enviado_em: string;
};

/** GET /sgd/demandas/{id}/documentos/ */
export async function listDocumentosDemanda(
  demandaId: number,
  signal?: AbortSignal,
): Promise<DocumentoDemanda[]> {
  const res = await apiClient(`${DEMANDAS_PATH}${demandaId}/documentos/`, { signal });
  return res.json();
}

/**
 * Três etapas: URL pré-assinada (com o tipo, que o backend confere contra o
 * perfil), PUT no storage e confirmação, que cria o `DemandDocument`.
 */
export async function enviarDocumentoDemanda(
  demandaId: number,
  arquivo: File,
  dados: { tipo: string; descricao: string; fornecedor: string },
  onProgress: (percent: number) => void,
  signal?: AbortSignal,
): Promise<DocumentoDemanda> {
  const pedido = await apiClient(`${DEMANDAS_PATH}${demandaId}/documentos/upload-url/`, {
    method: "POST",
    body: JSON.stringify({
      filename: arquivo.name,
      content_type: arquivo.type,
      size: arquivo.size,
      tipo: dados.tipo,
    }),
  });
  const { url, key } = (await pedido.json()) as { url: string; key: string };
  await uploadToStorage(url, arquivo, arquivo.type, onProgress, signal);
  if (signal?.aborted) throw new DOMException("Envio cancelado.", "AbortError");

  const res = await apiClient(`${DEMANDAS_PATH}${demandaId}/documentos/confirm/`, {
    method: "POST",
    body: JSON.stringify({
      key,
      tipo: dados.tipo,
      descricao: dados.descricao,
      fornecedor: dados.fornecedor,
      nome_original: arquivo.name,
    }),
  });
  return res.json();
}

/** DELETE /sgd/demandas/{id}/documentos/{doc}/ */
export async function removerDocumentoDemanda(demandaId: number, documentoId: number): Promise<void> {
  await apiClient(`${DEMANDAS_PATH}${demandaId}/documentos/${documentoId}/`, { method: "DELETE" });
}

/** GET /sgd/demandas/{id}/documentos/{doc}/download/ — URL pré-assinada, aberta em nova aba. */
export async function abrirDocumentoDemanda(demandaId: number, documentoId: number): Promise<void> {
  const res = await apiClient(`${DEMANDAS_PATH}${demandaId}/documentos/${documentoId}/download/`);
  const { url } = (await res.json()) as { url: string };
  window.open(url, "_blank", "noopener,noreferrer");
}

// ─── Cotações de equipamentos (§3.6) ─────────────────────────────────────────

export const COTACOES_MINIMAS = 3;

export const COTACOES_CONFERINDO = "Conferindo as cotações dos documentos da demanda…";

export const COTACOES_SEM_DOCUMENTOS =
  "Não foi possível conferir as cotações: a submissão fica bloqueada até a lista de documentos carregar.";

/**
 * A regra de `_exigir_minimo_cotacoes_equipamento`, conferida antes de chamar a
 * API: com solicitação de equipamento, ao menos 3 cotações, de fornecedores
 * distintos. Devolve o aviso, ou null quando está tudo certo.
 *
 * `documentos` indefinido é a lista ainda não carregada (ou que falhou, com
 * `falhou`): com equipamento, a regra não tem como ser conferida e a
 * submissão fica bloqueada.
 */
export function pendenciaDeCotacoes(
  demanda: Pick<Demanda, "solicitacoes">,
  documentos: Pick<DocumentoDemanda, "tipo" | "fornecedor">[] | undefined,
  falhou = false,
): string | null {
  if (!demanda.solicitacoes.some((s) => s.tipo === "equipamento")) return null;
  if (!documentos) return falhou ? COTACOES_SEM_DOCUMENTOS : COTACOES_CONFERINDO;
  const fornecedores = documentos.filter((d) => d.tipo === "cotacao").map((d) => d.fornecedor.trim());
  if (fornecedores.length < COTACOES_MINIMAS) {
    return `Aquisição de equipamentos exige ao menos ${COTACOES_MINIMAS} cotações em PDF — há ${fornecedores.length}.`;
  }
  if (new Set(fornecedores).size < fornecedores.length) {
    return "As cotações precisam ser de fornecedores distintos.";
  }
  return null;
}
