import { apiClient } from "./api";
import type { TipoTransacao } from "./orcamento";

/**
 * "Meu saldo" (#401, backend AJ-BE-06 / PR #414): quanto a própria pessoa
 * ainda pode solicitar em cada rubrica, pelo limite individual do período, e o
 * extrato dos lançamentos que formam esse saldo.
 */

export type SemaforoSaldo = "verde" | "amarelo" | "vermelho";

/** `MeuSaldoSerializer`. Decimais como string, datas `YYYY-MM-DD`. */
export type SaldoDaRubrica = {
  rubrica: string;
  rubrica_nome: string;
  /** Falso: rubrica inativa, que não recebe demanda nova, mas já teve movimento. */
  rubrica_ativa: boolean;
  limite: string;
  comprometido: string;
  executado: string;
  disponivel: string;
  semaforo: SemaforoSaldo;
  periodo_inicio: string;
  /** Nulo quando o período não tem fim (vigência sem data definida). */
  periodo_fim: string | null;
  dias_restantes: number | null;
  /** O saldo não usado passa para o período seguinte (`budget_limit_carry_over`). */
  acumula_saldo: boolean;
  /** Saldo do pool territorial — a segunda trava. Nulo sem pool no território. */
  saldo_territorio: string | null;
};

/** `LinhaDoExtratoSerializer`. */
export type LinhaDoExtrato = {
  id: number;
  tipo: TipoTransacao;
  valor: string;
  /** Quanto o lançamento mexeu no disponível, com sinal: reserva negativa, liberação positiva. */
  efeito: string;
  saldo_anterior: string | null;
  saldo_posterior: string | null;
  demanda_id: string | null;
  justificativa: string;
  criado_em: string;
  periodo_inicio: string | null;
  periodo_fim: string | null;
};

export type PaginaDoExtrato = { count: number; results: LinhaDoExtrato[] };

/** GET /api/v1/sgp/orcamento/meu-saldo/ — só as rubricas em que a pessoa tem limite. */
export async function fetchMeuSaldo(signal?: AbortSignal): Promise<SaldoDaRubrica[]> {
  const res = await apiClient("/api/v1/sgp/orcamento/meu-saldo/", { signal });
  return res.json();
}

/**
 * GET .../meu-saldo/{rubrica}/extrato/?limit=&offset=&historico= — do mais
 * recente ao mais antigo. Sem `historico`, só o período vigente. O limite que
 * só existe pelo padrão do perfil ainda não tem lançamento: o extrato vem vazio
 * até a primeira reserva.
 */
export async function fetchExtrato(
  rubrica: string,
  params: { offset: number; limit: number; historico: boolean },
  signal?: AbortSignal,
): Promise<PaginaDoExtrato> {
  const qs = new URLSearchParams({ limit: String(params.limit), offset: String(params.offset) });
  if (params.historico) qs.set("historico", "true");
  const res = await apiClient(
    `/api/v1/sgp/orcamento/meu-saldo/${encodeURIComponent(rubrica)}/extrato/?${qs}`,
    { signal },
  );
  return res.json();
}

/** O atalho de recurso extra (#321) só faz sentido quando o limite está apertando. */
export function pedeRecursoExtra(saldo: Pick<SaldoDaRubrica, "semaforo" | "rubrica_ativa">): boolean {
  return saldo.rubrica_ativa && (saldo.semaforo === "amarelo" || saldo.semaforo === "vermelho");
}
