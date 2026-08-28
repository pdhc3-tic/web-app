"use client";

import { useState } from "react";
import { ShieldAlert } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import {
  converterValorManual,
  formatarValor,
  valorParaTexto,
  type ConflitoDecisao,
  type ConflitoDetalhe,
  type ValorConflito,
} from "@/app/lib/conflitos";
import { ConfrontoValores } from "../../_components/ConfrontoValores";

type Props = {
  conflito: ConflitoDetalhe;
  salvando: boolean;
  erro: string | null;
  onResolver: (decisao: ConflitoDecisao, valorManual?: ValorConflito) => void;
};

/**
 * Escolha de qual valor prevalece.
 *
 * Não existe — nem pode existir — uma ação de "resolver automaticamente" aqui: o
 * backend resolve sozinho o que é resolvível sozinho, e o que chega a esta tela
 * chega justamente por exigir decisão humana. A única saída é escolher um valor.
 */
export function ResolucaoForm({ conflito, salvando, erro, onResolver }: Props) {
  const [decisao, setDecisao] = useState<ConflitoDecisao>("servidor");
  const [texto, setTexto] = useState(() => valorParaTexto(conflito.valor_servidor));
  const [erroLocal, setErroLocal] = useState<string | null>(null);

  // A referência de tipo é o valor do servidor quando existe; senão, o local.
  // É ele que decide se o texto digitado vira número, booleano ou string.
  const referencia =
    conflito.valor_servidor !== null && conflito.valor_servidor !== undefined
      ? conflito.valor_servidor
      : conflito.valor_local;

  function handleSubmit() {
    if (salvando) return;
    setErroLocal(null);

    if (decisao !== "manual") {
      onResolver(decisao);
      return;
    }

    const resultado = converterValorManual(texto, referencia);
    if ("erro" in resultado) {
      setErroLocal(resultado.erro);
      return;
    }
    onResolver("manual", resultado.valor);
  }

  return (
    <section
      data-testid="conflito-resolucao"
      className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-6"
    >
      <div className="flex flex-col gap-1">
        <h2 className="text-sm font-medium text-text">Qual valor deve prevalecer?</h2>
        <p className="text-sm text-text-muted">
          O valor escolhido é gravado no registro definitivo e o conflito sai da
          lista de pendentes. A decisão fica registrada em auditoria.
        </p>
      </div>

      {conflito.campo_sensivel && (
        <p
          data-testid="conflito-aviso-sensivel"
          className="flex items-start gap-2.5 rounded-md border border-error-text/30 bg-error-bg px-3 py-2.5 text-sm text-error-text"
        >
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            Campo sensível: a revisão manual é obrigatória. O sistema não resolve
            este conflito sozinho, e a escolha precisa ser conferida com o
            responsável pela coleta antes de confirmar.
          </span>
        </p>
      )}

      <ConfrontoValores
        valorLocal={conflito.valor_local}
        valorServidor={conflito.valor_servidor}
        destaque={decisao === "manual" ? null : decisao}
      />

      <fieldset className="flex flex-col gap-2" disabled={salvando}>
        <legend className="sr-only">Valor que deve prevalecer</legend>

        <Escolha
          testid="conflito-opcao-servidor"
          checked={decisao === "servidor"}
          onSelect={() => setDecisao("servidor")}
          titulo="Manter o valor do servidor"
          descricao={formatarValor(conflito.valor_servidor)}
        />
        <Escolha
          testid="conflito-opcao-local"
          checked={decisao === "local"}
          onSelect={() => setDecisao("local")}
          titulo="Adotar o valor do aparelho"
          descricao={formatarValor(conflito.valor_local)}
        />
        <Escolha
          testid="conflito-opcao-manual"
          checked={decisao === "manual"}
          onSelect={() => setDecisao("manual")}
          titulo="Informar outro valor"
          descricao="Quando nenhum dos dois está correto."
        />

        {decisao === "manual" && (
          <div className="pl-7 pt-1">
            <Input
              id="conflito-valor-manual"
              label="Novo valor"
              value={texto}
              onChange={(e) => {
                setTexto(e.target.value);
                setErroLocal(null);
              }}
              error={erroLocal ?? undefined}
              helperText={
                typeof referencia === "number"
                  ? "Campo numérico — use ponto ou vírgula para os decimais."
                  : undefined
              }
              data-testid="conflito-valor-manual"
            />
          </div>
        )}
      </fieldset>

      {erro && (
        <p
          data-testid="conflito-erro"
          role="alert"
          className="rounded-md bg-error-bg px-3 py-2 text-sm text-error-text"
        >
          {erro}
        </p>
      )}

      <div className="flex justify-end">
        <Button
          onClick={handleSubmit}
          loading={salvando}
          data-testid="conflito-confirmar"
        >
          Confirmar resolução
        </Button>
      </div>
    </section>
  );
}

function Escolha({
  testid,
  checked,
  onSelect,
  titulo,
  descricao,
}: {
  testid: string;
  checked: boolean;
  onSelect: () => void;
  titulo: string;
  descricao: string;
}) {
  return (
    <label
      data-testid={testid}
      className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors ${
        checked
          ? "border-primary bg-surface-muted"
          : "border-border hover:bg-surface-muted"
      }`}
    >
      <input
        type="radio"
        name="conflito-decisao"
        checked={checked}
        onChange={onSelect}
        className="mt-1 h-4 w-4 shrink-0 accent-[var(--color-primary)]"
      />
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="text-sm font-medium text-text">{titulo}</span>
        <span className="break-words text-xs text-text-muted">{descricao}</span>
      </span>
    </label>
  );
}
