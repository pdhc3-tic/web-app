import { apiClient } from "./api";

/**
 * Parâmetros globais do orçamento (#403, CORE-RF16/RF17), guardados em
 * `SystemConfig`: `GET /system-config/` e `PATCH /system-config/{chave}/`.
 * A UGP lê; só o Super Admin altera (`IsSuperAdminOrUGPReadOnly`).
 *
 * O backend valida só o tipo (inteiro, booleano) e aceita qualquer texto na
 * periodicidade. As opções e as faixas abaixo são conferidas aqui, antes de
 * enviar; validá-las também no backend é o item 6 do
 * `docs/pendencias-backend-sprint-12b.md`.
 */

export type ChaveParametro =
  | "budget_limit_period"
  | "budget_limit_carry_over"
  | "budget_overallocation_allowed"
  | "budget_subexec_alert_months"
  | "budget_subexec_min_pct"
  | "budget_transfer_alert_pct";

type Base = { chave: ChaveParametro; rotulo: string; ajuda: string };

export type DefinicaoParametro =
  | (Base & { controle: "opcoes"; opcoes: { value: string; label: string }[] })
  | (Base & { controle: "booleano" })
  | (Base & { controle: "inteiro"; min: number; max: number; unidade: string });

/** Os seis parâmetros da issue, na ordem em que a tela os mostra. */
export const PARAMETROS: DefinicaoParametro[] = [
  {
    chave: "budget_limit_period",
    rotulo: "Periodicidade dos limites de gasto",
    ajuda:
      "Vale para todo o projeto. Os limites criados a partir da mudança já usam a nova periodicidade; os que já existem mantêm as datas.",
    controle: "opcoes",
    opcoes: [
      { value: "mensal", label: "Mensal" },
      { value: "trimestral", label: "Trimestral" },
      { value: "semestral", label: "Semestral" },
      { value: "vigencia", label: "Vigência do projeto" },
    ],
  },
  {
    chave: "budget_limit_carry_over",
    rotulo: "Acumular saldo não utilizado",
    ajuda: "Ligado, o saldo que sobra do limite passa para o período seguinte. Desligado, ele expira.",
    controle: "booleano",
  },
  {
    chave: "budget_overallocation_allowed",
    rotulo: "Permitir sobrealocação de limites",
    ajuda:
      "Ligado, a soma dos limites individuais de um território pode passar do pool territorial. O bloqueio efetivo continua sendo o pool.",
    controle: "booleano",
  },
  {
    chave: "budget_subexec_alert_months",
    rotulo: "Antecedência do alerta de subexecução",
    ajuda: "Quantos meses antes do fim da vigência o sistema passa a alertar a subexecução.",
    controle: "inteiro",
    min: 1,
    max: 24,
    unidade: "meses",
  },
  {
    chave: "budget_subexec_min_pct",
    rotulo: "Execução mínima esperada",
    ajuda: "Abaixo deste percentual de execução, o alerta de subexecução dispara.",
    controle: "inteiro",
    min: 1,
    max: 100,
    unidade: "%",
  },
  {
    chave: "budget_transfer_alert_pct",
    rotulo: "Limite de remanejamento por rubrica",
    ajuda: "Volume remanejado de uma rubrica, em percentual do valor aprovado, que dispara o alerta de aditivo.",
    controle: "inteiro",
    min: 1,
    max: 100,
    unidade: "%",
  },
];

/**
 * O `valor` de `SystemConfigSerializer` sai convertido pelo `tipo`: número
 * nos inteiros, `true`/`false` nos booleanos e texto nos demais.
 */
export type ValorDeConfig = string | number | boolean | null;

/** `SystemConfigSerializer`. */
export type ConfigDoSistema = {
  chave: string;
  valor: ValorDeConfig;
  tipo: string;
  descricao: string;
  atualizado_por: string | null;
  atualizado_em: string | null;
};

/**
 * GET /api/v1/system-config/ — todas as chaves. A paginação padrão do backend
 * é de 10 por página (`LimitOffsetPagination`), então a tela pede um teto alto.
 */
export async function fetchConfigs(signal?: AbortSignal): Promise<ConfigDoSistema[]> {
  const res = await apiClient("/api/v1/system-config/?limit=200", { signal });
  const data: ConfigDoSistema[] | { results: ConfigDoSistema[] } = await res.json();
  return Array.isArray(data) ? data : data.results;
}

/** PATCH /api/v1/system-config/{chave}/ — só o valor muda. */
export async function salvarConfig(chave: ChaveParametro, valor: string): Promise<ConfigDoSistema> {
  const res = await apiClient(`/api/v1/system-config/${chave}/`, {
    method: "PATCH",
    body: JSON.stringify({ valor }),
  });
  return res.json();
}

/** O valor do backend como texto, qualquer que seja o tipo em que veio. */
function comoTexto(valor: ValorDeConfig | undefined): string {
  return valor === null || valor === undefined ? "" : String(valor).trim();
}

/** `true`, "True", "true" ou "1" do backend como booleano. */
export function paraBooleano(valor: ValorDeConfig | undefined): boolean {
  if (typeof valor === "boolean") return valor;
  const v = comoTexto(valor).toLowerCase();
  return v === "true" || v === "1";
}

/**
 * Confere tipo e faixa do valor digitado. Devolve a mensagem de erro, ou `null`
 * quando o valor pode ser enviado.
 */
export function validarParametro(def: DefinicaoParametro, valor: string): string | null {
  const v = valor.trim();
  if (def.controle === "opcoes") {
    return def.opcoes.some((o) => o.value === v) ? null : "Escolha uma das opções.";
  }
  if (def.controle === "booleano") {
    return v === "true" || v === "false" ? null : "Valor inválido.";
  }
  if (!/^\d+$/.test(v)) return "Informe um número inteiro.";
  const n = Number(v);
  if (n < def.min || n > def.max) return `Informe um valor entre ${def.min} e ${def.max}.`;
  return null;
}

/** O valor do backend na forma que o controle da tela usa. */
export function valorDeTela(def: DefinicaoParametro, valor: ValorDeConfig | undefined): string {
  if (def.controle === "booleano") return paraBooleano(valor) ? "true" : "false";
  return comoTexto(valor);
}
