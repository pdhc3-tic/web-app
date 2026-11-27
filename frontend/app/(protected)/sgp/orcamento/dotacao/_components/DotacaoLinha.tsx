"use client";

import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { formatCurrencyBRL, formatMoneyInput, moneyOrNull } from "@/app/lib/format";
import { pisoDoPool, valorNumerico } from "@/app/lib/orcamento";
import type { LinhaDotacao } from "./tipos";

type Props = {
  linha: LinhaDotacao;
  /** Valor digitado, já mascarado ("R$ 1.234,56"). */
  valor: string;
  onChange: (valor: string) => void;
  onGravar: () => void;
  /** Mensagem de 400 do servidor ancorada nesta rubrica, se houve. */
  erro?: string;
  salvando: boolean;
  /** Trava a linha enquanto outra está gravando. */
  desabilitado: boolean;
};

/**
 * Uma rubrica da dotação nacional: quanto tem hoje, quanto já desceu aos
 * estados, quanto passará a ter.
 *
 * Grava sozinha, como `DestinoLinha` da Distribuição: cada pool é um POST ou
 * PATCH próprio, sem endpoint de lote, e um "salvar tudo" deixaria um estado
 * parcial sem dizer onde parou.
 */
export function DotacaoLinha({ linha, valor, onChange, onGravar, erro, salvando, desabilitado }: Props) {
  const { rubrica, pool } = linha;
  const atual = pool ? valorNumerico(pool.valor_aprovado) : 0;
  const distribuido = pool ? valorNumerico(pool.valor_distribuido) : 0;
  const piso = pool ? pisoDoPool(pool) : 0;

  const vazio = valor.trim() === "";
  const pretendido = vazio ? null : Number(moneyOrNull(valor) ?? "0");
  // Gravar o valor que já está lá é uma requisição sem efeito.
  const inalterado = pretendido !== null && Math.abs(pretendido - atual) < 0.005;
  // Um pool novo com zero não lança nada; um pool que existe pode descer até o piso.
  const semValor = pretendido !== null && pretendido <= 0 && pool === null;
  // Espelho de `atualizar_valor_alocado`. A autoridade é o 400 do servidor.
  const abaixoDoPiso = pretendido !== null && pool !== null && pretendido < piso - 0.005;

  return (
    <li
      className="flex flex-col gap-2 border-t border-border px-4 py-3 first:border-t-0"
      data-testid={`dotacao-rubrica-${rubrica.slug}`}
    >
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-text">
            {rubrica.nome}
            {!rubrica.ativo && <span className="ml-2 text-xs font-normal text-text-muted">(inativa)</span>}
            {pool?.reserva_ugp && (
              <span className="ml-2 text-xs font-normal text-text-muted">· reserva da UGP</span>
            )}
          </p>
          <p className="mt-0.5 text-xs text-text-muted tabular-nums" data-testid={`dotacao-atual-${rubrica.slug}`}>
            {pool ? (
              <>
                Dotação hoje: {formatCurrencyBRL(atual)}
                {" · "}
                distribuído aos estados: {formatCurrencyBRL(distribuido)}
                {piso > 0 && (
                  <>
                    {" · "}
                    <span title="Distribuído aos estados + comprometido + executado — o piso desta dotação">
                      não pode baixar de {formatCurrencyBRL(piso)}
                    </span>
                  </>
                )}
              </>
            ) : (
              "Sem dotação lançada"
            )}
          </p>
        </div>

        <div className="w-48">
          <Input
            label="Valor aprovado"
            inputMode="numeric"
            value={valor}
            onChange={(e) => onChange(formatMoneyInput(e.target.value))}
            error={erro}
            disabled={desabilitado || salvando}
            placeholder="R$ 0,00"
            data-testid={`dotacao-valor-${rubrica.slug}`}
          />
        </div>

        {/* Largura fixa, como na Distribuição: "Lançar" e "Ajustar" têm tamanhos diferentes. */}
        <Button
          variant="secondary"
          className="w-28 justify-center"
          onClick={onGravar}
          loading={salvando}
          disabled={desabilitado || vazio || inalterado || semValor || abaixoDoPiso}
          data-testid={`dotacao-submit-${rubrica.slug}`}
        >
          {pool ? "Ajustar" : "Lançar"}
        </Button>
      </div>

      {abaixoDoPiso && !erro && (
        <p className="text-xs text-error-text" data-testid={`dotacao-motivo-${rubrica.slug}`}>
          {distribuido > 0
            ? `Abaixo do que já foi distribuído aos estados e consumido (${formatCurrencyBRL(piso)}). Reduza antes as distribuições.`
            : `Abaixo do que já foi comprometido e executado (${formatCurrencyBRL(piso)}).`}
        </p>
      )}
    </li>
  );
}
