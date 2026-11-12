import type { PoolOrcamentoApi } from "@/app/lib/orcamento";
import { valorNumerico } from "@/app/lib/orcamento";

/**
 * Um destino da distribuição — um estado (para a UGP) ou um território (para o
 * Articulador), com o pool que já existe para ele, se existir (#398).
 */
export type Destino = {
  /** Id do State ou do Territory, conforme o nível. */
  id: number;
  /** "Pernambuco (PE)" ou "Território do Sertão do Pajeú". */
  nome: string;
  /** O pool já gravado para este destino, ou null se ainda não existe. */
  pool: PoolOrcamentoApi | null;
};

/**
 * O teto contra o qual a tela valida, e suas parcelas.
 *
 * Espelha `_travar_pai_e_checar_teto` do backend: o que limita não é o valor
 * aprovado do pool de cima, e sim o SALDO dele (aprovado − comprometido −
 * executado), e a soma que precisa caber nesse saldo inclui todos os irmãos.
 */
export type Teto = {
  /**
   * O que o pool de cima tem alocado, bruto (`valor_aprovado`). É o total de que todas as outras
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
  /** Aprovado menos comprometido e executado do pai — quanto dele ainda pode descer. */
  saldoDoPai: number;
  /** `valor_distribuido` do pai: a soma dos pools de baixo já gravados. */
  jaDistribuido: number;
  /** O que sobra: `saldoDoPai − jaDistribuido`. Nunca negativo na prática. */
  disponivel: number;
};

/** Não há pai: o nível de cima ainda não foi distribuído para este recorte. */
export const SEM_PAI: unique symbol = Symbol("sem-pai");

export type ResolucaoTeto = Teto | typeof SEM_PAI;

/**
 * O teto a partir do pool de cima — o nacional, para a UGP distribuir entre os
 * estados; o do estado, para o Articulador distribuir entre os territórios
 * (#398). As parcelas vêm prontas do painel: `valor_distribuido` já é a soma
 * dos pools de baixo, e `saldo_disponivel` o que sobra.
 *
 * Sem pai (o nível de cima não tem pool nesta rubrica), não há teto, e o
 * backend recusaria a criação com "distribua o nível acima primeiro".
 */
export function tetoDoPool(pai: PoolOrcamentoApi | null | undefined): ResolucaoTeto {
  if (!pai || valorNumerico(pai.valor_aprovado) === 0) return SEM_PAI;
  const alocadoNoPai = valorNumerico(pai.valor_aprovado);
  const consumidoNoPai = valorNumerico(pai.valor_comprometido) + valorNumerico(pai.valor_executado);
  const saldoDoPai = alocadoNoPai - consumidoNoPai;
  const jaDistribuido = valorNumerico(pai.valor_distribuido);
  return { alocadoNoPai, consumidoNoPai, saldoDoPai, jaDistribuido, disponivel: saldoDoPai - jaDistribuido };
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
  return destino.pool ? valorNumerico(destino.pool.valor_aprovado) : 0;
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
    // o teto do backend também soma.
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
