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
  /** Excedente do destino em edição; 0 quando cabe. */
  excedente: number;
  /** Rótulo do nível de cima, para nomear de onde vem o teto. */
  origem: string;
};

function Parcela({
  rotulo,
  valor,
  destaque,
}: {
  rotulo: string;
  valor: number;
  destaque?: "positivo" | "negativo";
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
      <dd className={`text-sm font-semibold tabular-nums ${cor}`}>
        {formatCurrencyBRL(valor)}
      </dd>
    </div>
  );
}

/**
 * Barra de teto da distribuição (§5.3.2).
 *
 * Mostra as três parcelas que compõem a validação do servidor — saldo do nível
 * superior, o que já desceu, o que sobra — e projeta o efeito do que está sendo
 * digitado antes de qualquer requisição.
 *
 * A projeção é conveniência, não autoridade: `_checar_teto` roda dentro de uma
 * transação com `select_for_update` no pai, então entre o que esta barra
 * desenha e o POST cabe a distribuição de outra pessoa. Por isso a tela nunca
 * afirma que vai dar certo — ela só impede o erro óbvio.
 */
export function BarraSaldo({ teto, projetado, excedente, origem }: Props) {
  const estourou = excedente > 0;

  // Denominador é o saldo do pai: é contra ele que o backend compara. Com saldo
  // zero não há proporção a desenhar, e `null` deixa a ProgressBar indeterminada
  // em vez de fingir 0% ou 100%.
  const pct =
    teto.saldoDoPai > 0 ? (projetado / teto.saldoDoPai) * 100 : null;

  const restante = teto.saldoDoPai - projetado;

  return (
    <section
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
      data-testid="distribuicao-barra-saldo"
      data-estourou={estourou ? "sim" : "nao"}
    >
      <dl className="flex flex-wrap gap-x-8 gap-y-3">
        <Parcela rotulo={`Disponível em ${origem}`} valor={teto.saldoDoPai} />
        <Parcela rotulo="Já distribuído" valor={teto.jaDistribuido} />
        <Parcela
          rotulo={estourou ? "Restaria" : "Restará"}
          valor={restante}
          destaque={estourou ? "negativo" : restante > 0 ? "positivo" : undefined}
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
            Excede o disponível em{" "}
            <strong className="tabular-nums">
              {formatCurrencyBRL(excedente)}
            </strong>
            . Reduza o valor para poder distribuir.
          </span>
        </p>
      )}
    </section>
  );
}
