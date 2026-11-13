"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { formatDate } from "@/app/lib/datetime";
import {
  OPCOES_DE_ORIGEM,
  criarValor,
  registrarNovaVigencia,
  validarNovoValor,
  type FaixaDestino,
  type OrigemValorDiaria,
  type ValorDiaria,
} from "@/app/lib/diarias";
import { formatCurrencyBRL, formatMoneyInput, moneyOrNull } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";

export type AlvoDoValor = { faixa: FaixaDestino; atual: ValorDiaria | null };

type Props = { alvo: AlvoDoValor | null; onClose: () => void };

/** Remonta o formulário a cada alvo, para os campos começarem limpos. */
export function ValorDialog({ alvo, onClose }: Props) {
  return (
    <SlideOver
      open={alvo !== null}
      onClose={onClose}
      title={alvo?.atual ? "Editar valor da diária" : "Cadastrar valor da diária"}
    >
      {alvo && <Formulario key={`${alvo.faixa.id}:${alvo.atual?.id ?? "novo"}`} alvo={alvo} onClose={onClose} />}
    </SlideOver>
  );
}

/**
 * Valor da diária de uma faixa (#366). Editar não sobrescreve: pede a data de
 * início da nova vigência, e o backend encerra a atual na véspera.
 */
function Formulario({ alvo, onClose }: { alvo: AlvoDoValor; onClose: () => void }) {
  const { faixa, atual } = alvo;
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [valor, setValor] = useState("");
  const [inicio, setInicio] = useState("");
  const [origem, setOrigem] = useState<OrigemValorDiaria>("fgd");
  const [erros, setErros] = useState<{ valor?: string; vigencia_inicio?: string }>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);

  const salvar = useMutation({
    mutationFn: () => {
      const dados = { valor: moneyOrNull(valor) ?? "", vigencia_inicio: inicio, origem };
      return atual ? registrarNovaVigencia(atual.id, dados) : criarValor(faixa.id, dados);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: qk.diarias.valores });
      showToast(`Valor de "${faixa.nome}" registrado a partir de ${formatDate(inicio)}.`, "success");
      onClose();
    },
    onError: (e) => {
      if (!(e instanceof ApiError)) {
        setErroGeral("Não foi possível salvar o valor. Tente novamente.");
        return;
      }
      const porCampo = (campo: string) => e.fieldErrors?.find((f) => f.field === campo)?.message;
      const doServidor = { valor: porCampo("valor"), vigencia_inicio: porCampo("vigencia_inicio") };
      setErros(doServidor);
      setErroGeral(doServidor.valor || doServidor.vigencia_inicio ? null : e.message);
    },
  });

  function enviar(e: React.FormEvent) {
    e.preventDefault();
    const encontrados = validarNovoValor({ valor: moneyOrNull(valor), vigencia_inicio: inicio }, atual);
    setErros(encontrados);
    setErroGeral(null);
    if (Object.keys(encontrados).length === 0) salvar.mutate();
  }

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-5 px-4 py-4" data-testid="valor-diaria-form">
      <div>
        <p className="text-sm font-medium text-text">{faixa.nome}</p>
        {atual ? (
          <p className="mt-1 text-sm leading-relaxed text-text-muted" data-testid="valor-diaria-atual">
            Valor atual: {formatCurrencyBRL(atual.valor)}, em vigor desde {formatDate(atual.vigencia_inicio)}. Ele
            deixa de valer na véspera da data informada abaixo e continua no histórico. As solicitações já gravadas
            mantêm o valor com que foram calculadas.
          </p>
        ) : (
          <p className="mt-1 text-sm text-text-muted">Esta faixa ainda não tem valor vigente.</p>
        )}
      </div>

      <Input
        id="valor-diaria-valor"
        label="Novo valor da diária"
        inputMode="numeric"
        placeholder="R$ 0,00"
        required
        value={valor}
        onChange={(e) => setValor(formatMoneyInput(e.target.value))}
        error={erros.valor}
      />
      <Input
        id="valor-diaria-inicio"
        label="Início da nova vigência"
        type="date"
        required
        min={atual?.vigencia_inicio}
        value={inicio}
        onChange={(e) => setInicio(e.target.value)}
        error={erros.vigencia_inicio}
        helperText="O valor passa a valer nesta data, inclusive."
      />
      <Select
        id="valor-diaria-origem"
        label="Origem do valor"
        required
        options={OPCOES_DE_ORIGEM}
        value={origem}
        onChange={(v) => setOrigem(v as OrigemValorDiaria)}
      />

      {erroGeral && (
        <p
          role="alert"
          className="rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
          data-testid="valor-diaria-erro"
        >
          {erroGeral}
        </p>
      )}

      <div className="flex items-center justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onClose} disabled={salvar.isPending}>
          Cancelar
        </Button>
        <Button type="submit" loading={salvar.isPending} data-testid="valor-diaria-salvar">
          Salvar valor
        </Button>
      </div>
    </form>
  );
}
