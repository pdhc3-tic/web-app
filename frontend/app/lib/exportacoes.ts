import { apiClient } from "@/app/lib/api";
import { dispararDownload, nomeDoContentDisposition, type FormatoExport } from "@/app/lib/exportarPlano";

/**
 * Exportações assíncronas do SGP (A4 da #302), sobre `ExportacaoViewSet`
 * (backend/docs/export.md):
 *
 *   POST /api/v1/sgp/exportacoes/                {tipo, formato, filtros} → 202 ExportJob
 *   GET  /api/v1/sgp/exportacoes/{id}/           → o ExportJob (polling)
 *   GET  /api/v1/sgp/exportacoes/{id}/download/  → o arquivo; 409 se não terminou,
 *                                                  410 se expirou (vale 24 h)
 *   POST /api/v1/sgp/exportacoes/{id}/repetir/   → reenfileira um job em `erro`
 *
 * O Plano de Trabalho e as Atividades sempre geram em segundo plano. As UPFs
 * começam por `/upfs/exportar/`, que decide entre o arquivo na hora e o job
 * (`iniciarExportacaoUpfs`); a partir do job, o fluxo é este mesmo.
 */

export type TipoExportacao = "plano_trabalho" | "atividades" | "upfs";

/** Espelha `ExportJob.Status`. */
export type StatusExportacao = "pendente" | "processando" | "concluida" | "erro";

/** `ExportJobSerializer`. */
export type Exportacao = {
  id: number;
  tipo: TipoExportacao;
  formato: FormatoExport;
  filtros: Record<string, string>;
  status: StatusExportacao;
  /** 0–100. */
  progresso: number;
  /** Mensagem do backend quando `status === "erro"`; vazio nos outros casos. */
  erro: string;
  /** Total de registros no conjunto filtrado. */
  total_registros: number | null;
  nome_arquivo: string;
  criado_em: string;
  concluido_em: string | null;
  /** O arquivo da exportação concluída vale até aqui (24 h). */
  expira_em: string | null;
};

/** Como uma exportação começou: com o arquivo já baixado ou com o job na fila. */
export type ResultadoExportacao =
  | { tipo: "arquivo"; nome: string }
  | { tipo: "tarefa"; exportacao: Exportacao };

const EXPORTACOES_PATH = "/api/v1/sgp/exportacoes/";

export function emAndamento(e: Pick<Exportacao, "status">): boolean {
  return e.status === "pendente" || e.status === "processando";
}

/** Dispara o download do corpo da resposta e devolve o nome entregue. */
export async function baixarResposta(res: Response, nomePadrao: string): Promise<string> {
  const nome = nomeDoContentDisposition(res.headers.get("Content-Disposition")) ?? nomePadrao;
  dispararDownload(await res.blob(), nome);
  return nome;
}

/**
 * POST — cria o job. Os `filtros` seguem o contrato de cada tipo
 * (`services.exportacao.validar_filtros`): chave desconhecida é recusada.
 */
export async function criarExportacao(pedido: {
  tipo: TipoExportacao;
  formato: FormatoExport;
  filtros: Record<string, string | undefined>;
}): Promise<Exportacao> {
  const filtros = Object.fromEntries(
    Object.entries(pedido.filtros).filter((par): par is [string, string] => !!par[1]),
  );
  const res = await apiClient(EXPORTACOES_PATH, {
    method: "POST",
    body: JSON.stringify({ tipo: pedido.tipo, formato: pedido.formato, filtros }),
  });
  return res.json();
}

export async function fetchExportacao(id: number, signal?: AbortSignal): Promise<Exportacao> {
  const res = await apiClient(`${EXPORTACOES_PATH}${id}/`, { signal });
  return res.json();
}

/** O arquivo da exportação concluída. Um 410 (`exportacao_expirada`) chega como `ApiError`. */
export async function baixarExportacao(exportacao: Exportacao): Promise<string> {
  const res = await apiClient(`${EXPORTACOES_PATH}${exportacao.id}/download/`);
  return baixarResposta(res, exportacao.nome_arquivo || `${exportacao.tipo}.${exportacao.formato}`);
}

export async function repetirExportacao(id: number): Promise<Exportacao> {
  const res = await apiClient(`${EXPORTACOES_PATH}${id}/repetir/`, { method: "POST" });
  return res.json();
}
