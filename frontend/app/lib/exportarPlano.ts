import { apiClient } from "@/app/lib/api";

/**
 * Exportação do Plano de Trabalho (BE-9).
 *
 * `GET /api/v1/sgp/plano-trabalho/exportar/` devolve o arquivo PRONTO — CSV ou
 * XLSX — já restrito ao escopo territorial do usuário
 * (`apps/sgp/services/workplan_export.py`). A tela não monta planilha nenhuma:
 * entrega os filtros, recebe o binário e dispara o download.
 */

export type FormatoExport = "csv" | "xlsx";

export const FORMATO_OPTIONS = [
  { value: "csv", label: "CSV (.csv)" },
  { value: "xlsx", label: "Excel (.xlsx)" },
];

/**
 * Espelha `apps/sgp/serializers_workplan.py::WorkPlanExportQuerySerializer`.
 *
 * `meta_id` é um inteiro só — o endpoint não aceita lista. A exportação cobre
 * UMA Meta ou TODAS, igual ao filtro do painel.
 *
 * O painel também filtra por Situação, mas o endpoint de exportação não aceita
 * `status_execucao`: o arquivo sai sempre com todas as situações.
 */
export type ExportFiltros = {
  formato: FormatoExport;
  meta_id?: string;
  territorio_id?: string;
  periodo_inicio?: string;
  periodo_fim?: string;
};

const EXPORT_PATH = "/api/v1/sgp/plano-trabalho/exportar/";

/**
 * Teto de espera do lado do cliente.
 *
 * A view é síncrona e o backend garante em teste que 12 meses de dados saem em
 * menos de 60s (`test_exports_simulated_twelve_month_dataset_under_sixty_seconds`),
 * mesmo número do `proxy_read_timeout` padrão do nginx. Sem este limite, uma
 * requisição pendurada deixaria o modal girando para sempre.
 */
export const EXPORT_TIMEOUT_MS = 60_000;

/** Estourou `EXPORT_TIMEOUT_MS` — a UI mostra uma mensagem própria para o caso. */
export class ExportTimeoutError extends Error {
  constructor() {
    super("A geração do arquivo excedeu o tempo limite.");
    this.name = "ExportTimeoutError";
  }
}

/**
 * Lê o nome do arquivo do `Content-Disposition`.
 *
 * Devolve `null` quando o header não veio OU não pôde ser lido: em
 * desenvolvimento o browser está em `:3000` e a API em `:8080`, e o Django não
 * declara `CORS_EXPOSE_HEADERS`, então o header existe na resposta mas o JS não
 * o enxerga. Em produção o nginx serve `/api/` na mesma origem
 * (`NEXT_PUBLIC_API_URL` vazio) e o nome vem do backend, como manda a issue.
 */
export function nomeDoContentDisposition(header: string | null): string | null {
  if (!header) return null;
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
  if (!match) return null;
  const bruto = match[1].trim();
  try {
    return decodeURIComponent(bruto);
  } catch {
    return bruto;
  }
}

/**
 * Reproduz `plano_trabalho_{data}.{ext}` da view quando o header é ilegível.
 *
 * O relógio é o do cliente, então o timestamp pode diferir em segundos (e no
 * fuso) do que o backend gravaria. É a aproximação aceitável: sem ela o browser
 * batiza o download com o hash da blob URL, o que parece defeito.
 */
function nomeDerivadoLocalmente(formato: FormatoExport): string {
  const agora = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const data = [
    agora.getFullYear(),
    pad(agora.getMonth() + 1),
    pad(agora.getDate()),
  ].join("-");
  const hora = [
    pad(agora.getHours()),
    pad(agora.getMinutes()),
    pad(agora.getSeconds()),
  ].join("-");
  return `plano_trabalho_${data}_${hora}.${formato}`;
}

/** Entrega o blob ao browser por um <a download> descartável. */
function dispararDownload(blob: Blob, nome: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revogar no mesmo tick cancela a gravação em alguns browsers — o download
  // ainda não começou quando o click retorna.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/**
 * Baixa o Plano de Trabalho filtrado e devolve o nome do arquivo entregue.
 *
 * Lança `ExportTimeoutError` no estouro do tempo e `ApiError` nos erros da API
 * (o `apiClient` já converte o corpo de erro do DRF).
 */
export async function baixarPlanoTrabalho(
  filtros: ExportFiltros,
): Promise<string> {
  const { formato, ...resto } = filtros;
  const qs = new URLSearchParams({ formato });
  for (const [chave, valor] of Object.entries(resto)) {
    if (valor) qs.set(chave, valor);
  }

  let res: Response;
  try {
    res = await apiClient(`${EXPORT_PATH}?${qs.toString()}`, {
      signal: AbortSignal.timeout(EXPORT_TIMEOUT_MS),
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "TimeoutError") {
      throw new ExportTimeoutError();
    }
    throw e;
  }

  const nome =
    nomeDoContentDisposition(res.headers.get("Content-Disposition")) ??
    nomeDerivadoLocalmente(formato);

  dispararDownload(await res.blob(), nome);
  return nome;
}
