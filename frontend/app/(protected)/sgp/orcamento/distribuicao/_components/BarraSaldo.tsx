"use client";

import { AlertTriangle } from "lucide-react";
import { ProgressBar } from "@/app/components/ui/ProgressBar/ProgressBar";
import { formatCurrencyBRL } from "@/app/lib/format";
import type { Teto } from "./tipos";

type Props = {
  teto: Teto;
  /**
   * Quanto o usuário está tentando alocar agora, somado ao que já está
   * gravado nos outros destinos. Alimenta a projeção da barra enquanto ele
   * digita — é o "em tempo real" de §5.3.2.
   */
  projetado: number;
  /**
   * Excedente do CONJUNTO: o quanto `projetado` passa do saldo do pai. É o que
   * a barra anuncia, porque é o que ela desenha — o excedente de uma linha só
   * fica na linha.
   */
  excedente: number;
  /** Quantos destinos têm rascunho agora; nomeia o excedente conjunto. */
  emEdicao: number;
  /** Rótulo do nível de cima, para nomear de onde vem o teto. */
  origem: string;
};

function Parcela({
  rotulo,
  valor,
  destaque,
  detalhe,
  testId,
}: {
  rotulo: string;
  valor: number;
  destaque?: "positivo" | "negativo";
  /** Linha de apoio sob o valor — usada para mostrar o gravado sob a projeção. */
  detalhe?: string;
  testId?: string;
}) {
  const cor =
    destaque === "negativo"
      ? "text-error-text"
      : destaque === "positivo"
        ? "text-success-text"
        : "text-text";

  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-2xs font-medium uppercase tracking-wide text-text-muted">
        {rotulo}
      </dt>
      <dd className={`text-sm font-semibold tabular-nums ${cor}`} data-testid={testId}>
        {formatCurrencyBRL(valor)}
        {detalhe && (
          <span className="block text-2xs font-normal text-text-muted">
            {detalhe}
          </span>
        )}
      </dd>
    </div>
  );
}

/**
 * Barra de teto da distribuição (§5.3.2).
 *
 * Mostra a conta inteira do servidor, na ordem em que ela acontece:
 *
 *     alocado no pai − comprometido/executado − distribuído = disponível
 *
 * O "comprometido e executado" só aparece quando existe, mas o ALOCADO aparece
 * sempre. Antes a barra começava no saldo do pai (já líquido dos dois), e com
 * valores comprometidos o usuário via um teto menor do que o alocado sem nada
 * na tela explicando a diferença — a impressão era de que o sistema tinha
 * perdido dinheiro.
 *
 * A projeção é conveniência, não autoridade: `_checar_teto` roda dentro de uma
 * transação com `select_for_update` no pai, então entre o que esta barra
 * desenha e o POST cabe a distribuição de outra pessoa. Por isso a tela nunca
 * afirma que vai dar certo — ela só impede o erro óbvio.
 */
export function BarraSaldo({
  teto,
  projetado,
  excedente,
  emEdicao,
  origem,
}: Props) {
  const estourou = excedente > 0;

  // Denominador é o saldo do pai: é contra ele que o backend compara. Com saldo
  // zero não há proporção a desenhar, e `null` deixa a ProgressBar indeterminada
  // em vez de fingir 0% ou 100%.
  const pct =
    teto.saldoDoPai > 0 ? (projetado / teto.saldoDoPai) * 100 : null;

  const disponivel = teto.saldoDoPai - projetado;
  // Enquanto nada está sendo digitado a projeção é o próprio gravado; repetir o
  // número embaixo seria ruído.
  const projetaDiferente = Math.abs(projetado - teto.jaDistribuido) >= 0.005;

  return (
    <section
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
      data-testid="distribuicao-barra-saldo"
      data-estourou={estourou ? "sim" : "nao"}
    >
      <dl className="flex flex-wrap gap-x-8 gap-y-3">
        <Parcela
          rotulo={`Alocado em ${origem}`}
          valor={teto.alocadoNoPai}
          testId="distribuicao-alocado"
        />

        {/* Só quando existe: uma parcela zerada em toda tela sem execução
            transformaria a conta em ruído. */}
        {teto.consumidoNoPai > 0 && (
          <Parcela
            rotulo="Comprometido e executado"
            valor={teto.consumidoNoPai}
            detalhe="não desce para os destinos"
            testId="distribuicao-consumido"
          />
        )}

        <Parcela
          rotulo="Distribuído"
          valor={projetado}
          detalhe={
            projetaDiferente
              ? `gravado hoje: ${formatCurrencyBRL(teto.jaDistribuido)}`
              : undefined
          }
          testId="distribuicao-distribuido"
        />

        <Parcela
          rotulo="Disponível"
          valor={disponivel}
          destaque={
            estourou ? "negativo" : disponivel > 0 ? "positivo" : undefined
          }
          testId="distribuicao-disponivel"
        />
      </dl>

      <ProgressBar
        value={pct}
        tone={estourou ? "error" : pct !== null && pct >= 90 ? "warning" : "primary"}
        label={`Distribuição de ${origem}`}
        valueText={`${formatCurrencyBRL(projetado)} de ${formatCurrencyBRL(
          teto.saldoDoPai,
        )}`}
      />

      {/* O excedente vem por texto, não só pela cor da barra: mesma regra de
          acessibilidade do semáforo do painel. */}
      {estourou && (
        <p
          role="alert"
          className="flex items-start gap-2 text-xs leading-relaxed text-error-text"
          data-testid="distribuicao-excedente"
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            {emEdicao > 1 ? (
              <>
                Os {emEdicao} valores em edição somam{" "}
                <strong className="tabular-nums">
                  {formatCurrencyBRL(excedente)}
                </strong>{" "}
                acima do disponível. Cada gravação é validada sozinha, então a
                primeira passaria e a seguinte seria recusada — reduza um dos
                destinos antes de distribuir.
              </>
            ) : (
              <>
                Excede o disponível em{" "}
                <strong className="tabular-nums">
                  {formatCurrencyBRL(excedente)}
                </strong>
                . Reduza o valor para poder distribuir.
              </>
            )}
          </span>
        </p>
      )}
    </section>
  );
}
