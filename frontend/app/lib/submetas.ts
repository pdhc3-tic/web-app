import { apiClient } from "@/app/lib/api";
import type { Schema } from "@/app/lib/apiSchema";

/**
 * Submetas do Plano de Trabalho (#431): o nível entre a Meta e a Ação
 * (Meta → Submeta → Ação). A Ação exige uma Submeta, então uma Meta sem
 * Submetas não recebe Ação.
 *
 * Quem decide é o backend (`WorkPlanSubmeta.clean`): número X.Y com o prefixo
 * da Meta, único na Meta, e período contido no dela. A tela confere o mesmo
 * antes de enviar, só para avisar sem ida ao servidor.
 */

/** `WorkPlanSubmetaSerializer`. */
export type Submeta = Schema<"WorkPlanSubmeta">;

/** Corpo do `POST /sgp/submetas/`: `WorkPlanSubmetaRequest`. */
export type SubmetaPayload = Schema<"WorkPlanSubmetaRequest">;

/** Formato do número da Submeta (`validate_numero_submeta`): X.Y. */
export const NUMERO_SUBMETA_RE = /^\d+\.\d+$/;

/** POST /api/v1/sgp/submetas/ — UGP e Super Admin. */
export async function criarSubmeta(payload: SubmetaPayload): Promise<Submeta> {
  const res = await apiClient("/api/v1/sgp/submetas/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.json();
}

/**
 * O próximo número livre na Meta: "3.1" na primeira, "3.4" depois de 3.1 a 3.3.
 * É só uma sugestão para o campo; quem confere a unicidade é o backend.
 */
export function proximoNumeroDeSubmeta(metaNumero: number | string, existentes: Pick<Submeta, "numero">[]): string {
  const prefixo = `${metaNumero}.`;
  const maior = existentes.reduce((m, s) => {
    if (!s.numero.startsWith(prefixo)) return m;
    const y = Number(s.numero.slice(prefixo.length));
    return Number.isInteger(y) && y > m ? y : m;
  }, 0);
  return `${prefixo}${maior + 1}`;
}

export type FormSubmeta = {
  numero: string;
  titulo: string;
  descricao: string;
  data_inicio: string;
  data_fim: string;
};

/** A Meta dona da Submeta: o número e o período que limitam os dela. */
export type MetaDaSubmeta = { id: number; numero: number | string; data_inicio: string; data_fim: string };

const dataBr = (iso: string) => iso.split("-").reverse().join("/");

/** As mesmas regras de `WorkPlanSubmeta.clean`, antes do envio. */
export function validarSubmeta(f: FormSubmeta, meta: MetaDaSubmeta): Partial<Record<keyof FormSubmeta, string>> {
  const erros: Partial<Record<keyof FormSubmeta, string>> = {};
  const numero = f.numero.trim();
  if (!numero) erros.numero = "Informe o número da Submeta.";
  else if (!NUMERO_SUBMETA_RE.test(numero)) erros.numero = "Formato inválido. Use X.Y (ex: 1.1, 2.3).";
  else if (!numero.startsWith(`${meta.numero}.`)) {
    erros.numero = `O número da Submeta deve começar com ${meta.numero}. (número da Meta).`;
  }

  if (!f.titulo.trim()) erros.titulo = "Informe o título da Submeta.";
  if (!f.data_inicio) erros.data_inicio = "Informe a data de início.";
  if (!f.data_fim) erros.data_fim = "Informe a data de término.";

  // "YYYY-MM-DD" compara certo como texto.
  if (f.data_inicio && f.data_fim) {
    if (f.data_fim < f.data_inicio) {
      erros.data_fim = "A data de término não pode ser anterior à de início.";
    } else if (f.data_inicio < meta.data_inicio || f.data_fim > meta.data_fim) {
      erros.data_inicio = `O período da Submeta deve estar contido no período da Meta (${dataBr(meta.data_inicio)} a ${dataBr(meta.data_fim)}).`;
    }
  }
  return erros;
}

export function payloadDaSubmeta(f: FormSubmeta, metaId: number): SubmetaPayload {
  return {
    meta: metaId,
    numero: f.numero.trim(),
    titulo: f.titulo.trim(),
    descricao: f.descricao.trim(),
    data_inicio: f.data_inicio,
    data_fim: f.data_fim,
  };
}
