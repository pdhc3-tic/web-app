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
  /**
   * O que o nível de cima tem alocado, bruto: `valor_aprovado` da linha
   * nacional ou `valor_alocado` da estadual. É o total de que todas as outras
   * parcelas são dedução — sem ele a barra mostraria um "disponível" menor que
   * o alocado e nada na tela explicaria a diferença.
   */
  alocadoNoPai: number;
  /**
   * `valor_comprometido + valor_executado` do pai. O que já saiu por demanda ou
   * pagamento não desce para os filhos, e é isso que separa `alocadoNoPai` de
   * `saldoDoPai`.
   */
  consumidoNoPai: number;
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

  const consumidoNoPai =
    valorNumerico(rubrica.valor_comprometido) +
    valorNumerico(rubrica.valor_executado);
  const saldoDoPai = aprovado - consumidoNoPai;
  const jaDistribuido = valorNumerico(rubrica.valor_distribuido);

  return {
    alocadoNoPai: aprovado,
    consumidoNoPai,
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

  const alocadoNoPai = valorNumerico(pai.valor_alocado);
  const consumidoNoPai =
    valorNumerico(pai.valor_comprometido) + valorNumerico(pai.valor_executado);
  const saldoDoPai = alocadoNoPai - consumidoNoPai;

  const jaDistribuido = rubrica.detalhamento
    .filter(
      (a) =>
        a.nivel === "territorial" &&
        a.territorio !== null &&
        (estadosPorTerritorio.get(a.territorio.id) ?? []).includes(siglaEstado),
    )
    .reduce((soma, a) => soma + valorNumerico(a.valor_alocado), 0);

  return {
    alocadoNoPai,
    consumidoNoPai,
    saldoDoPai,
    jaDistribuido,
    disponivel: saldoDoPai - jaDistribuido,
  };
}

/**
 * A projeção da distribuição inteira: o que cada destino passará a valer, o que
 * isso soma, e quem estoura.
 *
 * A conta é feita para o CONJUNTO, e não destino a destino, porque editar duas
 * linhas ao mesmo tempo é normal — e dois valores que cabem isoladamente podem
 * não caber juntos. Calculando só o excedente individual, a barra projetava um
 * total acima do teto enquanto os dois botões seguiam habilitados: a tela
 * afirmava o estouro e permitia a gravação na mesma renderização.
 *
 * Os dois excedentes existem porque respondem a perguntas diferentes:
 *
 * - `excedentePorDestino` é o que o servidor diria AGORA, ao gravar só esta
 *   linha: `_checar_teto` compara contra o que está no banco, onde os outros
 *   rascunhos ainda não entraram.
 * - `excedenteConjunto` é o que sobra de errado depois que todos forem
 *   gravados. Cada POST é validado sozinho, então o primeiro passa e o
 *   segundo leva 400 — avisar antes é o ponto do "tempo real" de §5.3.2.
 *
 * Uma linha em edição é bloqueada por qualquer um dos dois.
 */
export type Projecao = {
  /** Soma de todos os destinos com os rascunhos aplicados sobre os gravados. */
  total: number;
  /** Quanto `total` passa de `saldoDoPai`; 0 quando cabe. */
  excedenteConjunto: number;
  /** Por destino em edição, o excedente que a gravação isolada dele produziria. */
  excedentePorDestino: Record<number, number>;
  /** Ids dos destinos com rascunho — os que o excedente conjunto bloqueia. */
  emEdicao: number[];
};

function jaGravado(destino: Destino): number {
  return destino.alocacao ? valorNumerico(destino.alocacao.valor_alocado) : 0;
}

/**
 * @param rascunhos Valor digitado por destino, já convertido para número.
 *   Ausente (ou `undefined`) significa "linha intocada": vale o que está
 *   gravado.
 */
export function projetar(
  teto: Teto,
  destinos: Destino[],
  rascunhos: Record<number, number | undefined>,
): Projecao {
  let total = 0;
  const emEdicao: number[] = [];

  for (const destino of destinos) {
    const rascunho = rascunhos[destino.id];
    if (rascunho === undefined) {
      total += jaGravado(destino);
    } else {
      total += rascunho;
      emEdicao.push(destino.id);
    }
  }

  const excedentePorDestino: Record<number, number> = {};
  for (const destino of destinos) {
    const rascunho = rascunhos[destino.id];
    if (rascunho === undefined) continue;
    // Sem excluir o próprio destino, aumentar de 1.000 para 1.100 pareceria
    // consumir 1.100 de saldo novo, e a tela bloquearia uma gravação que o
    // servidor aceitaria. `jaDistribuido` vem do agregado da API, que é o que
    // `_checar_teto` também soma.
    const outros = teto.jaDistribuido - jaGravado(destino);
    excedentePorDestino[destino.id] = Math.max(
      0,
      outros + rascunho - teto.saldoDoPai,
    );
  }

  return {
    total,
    excedenteConjunto: Math.max(0, total - teto.saldoDoPai),
    excedentePorDestino,
    emEdicao,
  };
}
