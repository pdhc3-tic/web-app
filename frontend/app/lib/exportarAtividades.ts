import { apiClient } from "@/app/lib/api";
import { ExportTimeoutError, EXPORT_TIMEOUT_MS, nomeDoContentDisposition } from "@/app/lib/exportarPlano";
import type { FormatoExport } from "@/app/lib/exportarPlano";

export type ExportAtividadesFiltros = {
  formato: FormatoExport;
  periodo_inicio?: string;
  periodo_fim?: string;
  territorio_id?: string;
  acao_id?: string;
};

const EXPORT_PATH = "/api/v1/sgp/atividades/exportar/";

function nomeDerivado(formato: FormatoExport): string {
  const agora = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const data = [agora.getFullYear(), pad(agora.getMonth() + 1), pad(agora.getDate())].join("-");
  const hora = [pad(agora.getHours()), pad(agora.getMinutes()), pad(agora.getSeconds())].join("-");
  return `atividades_${data}_${hora}.${formato}`;
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

export async function baixarAtividades(filtros: ExportAtividadesFiltros): Promise<string> {
  const { formato, ...resto } = filtros;
  const qs = new URLSearchParams({ formato });
  for (const [chave, valor] of Object.entries(resto)) {
    if (valor) qs.set(chave, valor);
  }

  let res: Response;
  try {
    res = await apiClient(`${EXPORT_PATH}?${qs}`, {
      signal: AbortSignal.timeout(EXPORT_TIMEOUT_MS),
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "TimeoutError") throw new ExportTimeoutError();
    throw e;
  }

  const nome = nomeDoContentDisposition(res.headers.get("Content-Disposition")) ?? nomeDerivado(formato);
  dispararDownload(await res.blob(), nome);
  return nome;
}
