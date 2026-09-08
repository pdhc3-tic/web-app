"use client";

import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { formatCurrencyBRL, formatMoneyInput, moneyOrNull } from "@/app/lib/format";
import { valorNumerico } from "@/app/lib/orcamento";
import type { Destino } from "./tipos";

type Props = {
  destino: Destino;
  /** Valor digitado, já mascarado ("R$ 1.234,56"). */
  valor: string;
  onChange: (valor: string) => void;
  onDistribuir: () => void;
  /** Excedente deste destino; 0 quando cabe. */
  excedente: number;
  /** Mensagem de 400 do servidor ancorada neste destino, se houve. */
  erro?: string;
  salvando: boolean;
  /** Trava tudo enquanto outra linha está gravando. */
  desabilitado: boolean;
};

/**
 * Uma linha da distribuição: destino, quanto tem hoje, quanto passará a ter.
 *
 * Cada linha grava sozinha. O backend não tem endpoint de lote — cada alocação
 * é um POST ou PATCH próprio —, então um botão "salvar tudo" seria N
 * requisições sem atomicidade: falhando a terceira, as duas primeiras já teriam
 * gravado e o usuário ficaria sem saber onde parou. Num formulário que mexe no
 * teto do TED, o passo curto e confirmado é o que evita o estado parcial.
 */
export function DestinoLinha({
  destino,
  valor,
  onChange,
  onDistribuir,
  excedente,
  erro,
  salvando,
  desabilitado,
}: Props) {
  const atual = destino.alocacao
    ? valorNumerico(destino.alocacao.valor_alocado)
    : 0;
  const comprometido = destino.alocacao
    ? valorNumerico(destino.alocacao.valor_comprometido) +
      valorNumerico(destino.alocacao.valor_executado)
    : 0;

  const estourou = excedente > 0;
  const vazio = valor.trim() === "";
  // Gravar o mesmo valor que já está lá é uma requisição sem efeito; o botão
  // fica fora enquanto nada mudou.
  const inalterado =
    !vazio && Math.abs(Number(moneyOrNull(valor) ?? "0") - atual) < 0.005;

  return (
    <li
      className="flex flex-col gap-2 border-t border-border px-4 py-3 first:border-t-0"
      data-testid={`distribuicao-destino-${destino.id}`}
      data-estourou={estourou ? "sim" : "nao"}
    >
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-text">
            {destino.nome}
          </p>
          <p className="mt-0.5 text-xs text-text-muted tabular-nums">
            {destino.alocacao ? (
              <>
                Alocado hoje: {formatCurrencyBRL(atual)}
                {comprometido > 0 && (
                  <>
                    {" · "}
                    <span title="Comprometido + executado — o piso desta alocação">
                      não pode baixar de {formatCurrencyBRL(comprometido)}
                    </span>
                  </>
                )}
              </>
            ) : (
              "Sem alocação — será criada"
            )}
          </p>
        </div>

        <div className="w-44">
          <Input
            label="Valor"
            inputMode="numeric"
            value={valor}
            onChange={(e) => onChange(formatMoneyInput(e.target.value))}
            error={erro}
            disabled={desabilitado || salvando}
            placeholder="R$ 0,00"
            data-testid={`distribuicao-valor-${destino.id}`}
          />
        </div>

        <Button
          variant="secondary"
          onClick={onDistribuir}
          loading={salvando}
          // O bloqueio pelo teto é o critério de §5.3.2; a autoridade continua
          // sendo o 400 do servidor, que esta tela ancora no input acima.
          disabled={desabilitado || estourou || vazio || inalterado}
          data-testid={`distribuicao-submit-${destino.id}`}
        >
          {destino.alocacao ? "Ajustar" : "Distribuir"}
        </Button>
      </div>
    </li>
  );
}
