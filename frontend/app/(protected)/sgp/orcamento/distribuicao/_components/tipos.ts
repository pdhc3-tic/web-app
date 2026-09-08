import type { AlocacaoApi, RubricaOrcamentoApi } from "@/app/lib/orcamento";
import { valorNumerico } from "@/app/lib/orcamento";

/**
 * Um destino da distribuição — um estado (para a UGP) ou um território (para o
 * Articulador), com a alocação que já existe para ele, se existir.
 */
export type Destino = {
  /** Id do State ou do Territory, conforme o nível. */
  id: number;
  /** "Pernambuco (PE)" ou "Território do Sertão do Pajeú". */
  nome: string;
  /** A alocação já gravada para este destino, ou null se ainda não existe. */
  alocacao: AlocacaoApi | null;
};

/**
 * O teto contra o qual a tela valida, e suas parcelas.
 *
 * Espelha `_checar_teto` do backend: o que limita não é o valor aprovado do
 * nível de cima, e sim o SALDO dele (aprovado − comprometido − executado), e a
 * soma que precisa caber nesse saldo inclui todos os irmãos do mesmo nível.
 */
export type Teto = {
  /** `_saldo_disponivel(pai)` — quanto do pai ainda pode descer. */
  saldoDoPai: number;
  /** Soma do `valor_alocado` de todos os destinos já gravados. */
  jaDistribuido: number;
  /** O que sobra: `saldoDoPai − jaDistribuido`. Nunca negativo na prática. */
  disponivel: number;
};

/** Não há pai: o nível de cima ainda não foi distribuído para este recorte. */
export const SEM_PAI: unique symbol = Symbol("sem-pai");

export type ResolucaoTeto = Teto | typeof SEM_PAI;

/**
 * Teto do nível ESTADUAL: o pai é a linha nacional, e o endpoint já entrega os
 * agregados dela prontos.
 *
 * `valor_aprovado`, `valor_comprometido` e `valor_executado` de
 * `BudgetRubricaOrcamentoSerializer` são sempre do nacional (documentado em
 * `RubricaOrcamentoApi`), e `valor_distribuido` é a soma das estaduais — as
 * três parcelas do teto sem precisar varrer o detalhamento.
 */
export function tetoEstadual(rubrica: RubricaOrcamentoApi): ResolucaoTeto {
  const aprovado = valorNumerico(rubrica.valor_aprovado);
  // Sem linha nacional não há teto contra o que validar, e o backend recusaria
  // a criação com "distribua o nível acima primeiro".
  if (aprovado === 0) return SEM_PAI;

  const saldoDoPai =
    aprovado -
    valorNumerico(rubrica.valor_comprometido) -
    valorNumerico(rubrica.valor_executado);
  const jaDistribuido = valorNumerico(rubrica.valor_distribuido);

  return {
    saldoDoPai,
    jaDistribuido,
    disponivel: saldoDoPai - jaDistribuido,
  };
}

/**
 * Teto do nível TERRITORIAL: o pai é a alocação estadual do estado escolhido, e
 * os irmãos são os territórios que cobrem esse mesmo estado.
 *
 * O filtro por sigla não é decoração: `_peers_sob_mesmo_pai` usa
 * `territorio__estados__contains=[pai.estado.sigla]`, porque um território pode
 * cobrir mais de um estado e consumir o saldo de mais de um pai.
 */
export function tetoTerritorial(
  rubrica: RubricaOrcamentoApi,
  siglaEstado: string,
  estadosPorTerritorio: Map<number, string[]>,
): ResolucaoTeto {
  const pai = rubrica.detalhamento.find(
    (a) => a.nivel === "estadual" && a.estado?.sigla === siglaEstado,
  );
  if (!pai) return SEM_PAI;

  const saldoDoPai =
    valorNumerico(pai.valor_alocado) -
    valorNumerico(pai.valor_comprometido) -
    valorNumerico(pai.valor_executado);

  const jaDistribuido = rubrica.detalhamento
    .filter(
      (a) =>
        a.nivel === "territorial" &&
        a.territorio !== null &&
        (estadosPorTerritorio.get(a.territorio.id) ?? []).includes(siglaEstado),
    )
    .reduce((soma, a) => soma + valorNumerico(a.valor_alocado), 0);

  return {
    saldoDoPai,
    jaDistribuido,
    disponivel: saldoDoPai - jaDistribuido,
  };
}

/**
 * Quanto o valor pretendido para UM destino excede o teto — 0 quando cabe.
 *
 * O que entra na conta é a soma dos OUTROS destinos mais o pretendido, e não o
 * "disponível" cru: editar um destino que já tem valor gravado devolve o valor
 * antigo ao bolo. Sem excluir o próprio destino, aumentar de 1.000 para 1.100
 * pareceria consumir 1.100 de saldo novo, e a tela bloquearia uma operação que
 * o servidor aceitaria.
 */
export function excedente(
  teto: Teto,
  destino: Destino,
  valorPretendido: number,
): number {
  const doProprioDestino = destino.alocacao
    ? valorNumerico(destino.alocacao.valor_alocado)
    : 0;
  const outros = teto.jaDistribuido - doProprioDestino;
  const total = outros + valorPretendido;
  return Math.max(0, total - teto.saldoDoPai);
}
