import { apiClient } from "@/app/lib/api";
import { dispararDownload, nomeDoContentDisposition } from "@/app/lib/exportarPlano";
import { requestUploadUrl, uploadToStorage } from "@/app/components/sgp/PhotoUploader/photoUpload";

/**
 * Integração com o Arlo (#298 · SGD-FE-5), sobre o `ArloViewSet` (BE-4, PR #330):
 * exportação das demandas autorizadas, importação do retorno de pagamento e o
 * histórico das duas operações.
 */

const ARLO_PATH = "/api/v1/sgd/arlo/";

export type TipoOperacaoArlo = "exportacao" | "importacao";
export type StatusOperacaoArlo = "pendente" | "processando" | "concluido" | "falhou";

/** Uma linha do arquivo importado que o backend recusou — as demais seguem. */
export type ErroLinhaArlo = {
  linha: number;
  /** Campo do mapeamento que causou o erro; `null` quando é da linha toda. */
  campo: string | null;
  erro: string;
};

/** Espelha `ArloImportSerializer`. */
export type OperacaoArlo = {
  id: number;
  tipo: TipoOperacaoArlo;
  tipo_display: string;
  status: StatusOperacaoArlo;
  status_display: string;
  arquivo_url: string;
  nome_original: string;
  operado_por: number | null;
  operado_por_nome: string | null;
  operado_em: string;
  total_registros: number;
  registros_ok: number;
  erros_json: ErroLinhaArlo[];
  mapeamento_snapshot: Record<string, unknown>;
};

/** A importação roda numa task: enquanto não termina, a tela acompanha. */
export function operacaoEmAndamento(op: Pick<OperacaoArlo, "status">): boolean {
  return op.status === "pendente" || op.status === "processando";
}

/** GET /api/v1/sgd/arlo/ — histórico, mais recente primeiro. */
export async function listOperacoesArlo(signal?: AbortSignal): Promise<OperacaoArlo[]> {
  const res = await apiClient(ARLO_PATH, { signal });
  return res.json();
}

/** GET /api/v1/sgd/arlo/{id}/ */
export async function getOperacaoArlo(id: number, signal?: AbortSignal): Promise<OperacaoArlo> {
  const res = await apiClient(`${ARLO_PATH}${id}/`, { signal });
  return res.json();
}

/**
 * Nome usado quando o `Content-Disposition` não é legível: o backend ainda não
 * declara `CORS_EXPOSE_HEADERS` (docs/pendencias-backend-sprint-10.md, item 2).
 */
function nomeDerivadoExportacao(): string {
  const agora = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const data = [agora.getFullYear(), pad(agora.getMonth() + 1), pad(agora.getDate())].join("-");
  return `arlo_exportacao_${data}.csv`;
}

/**
 * POST /api/v1/sgd/arlo/exportar/ — gera o CSV de TODAS as demandas autorizadas
 * (uma linha por solicitação) e registra a operação no histórico. Dispara o
 * download e devolve o nome do arquivo entregue.
 */
export async function exportarParaArlo(): Promise<string> {
  const res = await apiClient(`${ARLO_PATH}exportar/`, { method: "POST" });
  const nome = nomeDoContentDisposition(res.headers.get("Content-Disposition")) ?? nomeDerivadoExportacao();
  dispararDownload(await res.blob(), nome);
  return nome;
}

/** Formatos que o `ArloUploadURLSerializer` aceita, com o limite de 10 MB. */
export const ARLO_TIPOS_ACEITOS: Record<string, string> = {
  "text/csv": ".csv",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
};
export const ARLO_TAMANHO_MAXIMO = 10 * 1024 * 1024;

/**
 * O Windows às vezes entrega o CSV como `application/vnd.ms-excel` ou sem tipo;
 * o backend só aceita os dois tipos acima, então o tipo sai da extensão.
 */
export function tipoDoArquivoArlo(file: File): string | null {
  const nome = file.name.toLowerCase();
  if (nome.endsWith(".csv")) return "text/csv";
  if (nome.endsWith(".xlsx")) {
    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  }
  return null;
}

/**
 * Envia a planilha de retorno em três etapas: pedir a URL pré-assinada, subir o
 * arquivo (o progresso do envio é reportado aqui) e confirmar. O backend
 * responde 202 com a operação `pendente`; o processamento segue numa task, que
 * a tela acompanha por `getOperacaoArlo`.
 */
export async function importarRetornoArlo(
  file: File,
  contentType: string,
  onProgress: (percent: number) => void,
  signal?: AbortSignal,
): Promise<OperacaoArlo> {
  const { url, key } = await requestUploadUrl(`${ARLO_PATH}importar/upload-url/`, {
    name: file.name,
    type: contentType,
    size: file.size,
  });
  await uploadToStorage(url, file, contentType, onProgress, signal);
  if (signal?.aborted) throw new DOMException("Envio cancelado.", "AbortError");

  const res = await apiClient(`${ARLO_PATH}importar/`, {
    method: "POST",
    body: JSON.stringify({ key, nome_original: file.name }),
  });
  return res.json();
}
