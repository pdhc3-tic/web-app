"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { REGRAS_DE_CONTAGEM, salvarParametros, type ParametrosDiarias } from "@/app/lib/diarias";
import { formatCurrencyBRL, formatMoneyInput, moneyOrNull } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";

/**
 * Parâmetros de contagem das diárias (#366): regras de meia diária e adicional
 * de embarque e desembarque. O padrão é o federal (Decreto 5.992/2006), com
 * tudo ligado menos o adicional. A página remonta este bloco quando os valores
 * salvos mudam.
 */
export function ParametrosContagem({ parametros }: { parametros: ParametrosDiarias }) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [form, setForm] = useState(parametros);
  const [adicional, setAdicional] = useState(formatCurrencyBRL(parametros.adicional_embarque_valor));
  const [erro, setErro] = useState<string | null>(null);

  const valorDoAdicional = moneyOrNull(adicional) ?? "0.00";
  const mudou =
    REGRAS_DE_CONTAGEM.some(({ chave }) => form[chave] !== parametros[chave]) ||
    form.adicional_embarque_ativo !== parametros.adicional_embarque_ativo ||
    Number(valorDoAdicional) !== Number(parametros.adicional_embarque_valor);

  // Sem diária inteira por pernoite, o backend conta um dia por diária e ignora as meias.
  const meiasSemEfeito = !form.regra_inteira_por_pernoite;
  const adicionalSemValor = form.adicional_embarque_ativo && Number(valorDoAdicional) <= 0;

  const salvar = useMutation({
    mutationFn: () => salvarParametros({ ...form, adicional_embarque_valor: valorDoAdicional }),
    onSuccess: async () => {
      setErro(null);
      await queryClient.invalidateQueries({ queryKey: qk.diarias.parametros });
      // A contagem mudou: a simulação já calculada no formulário de diárias deixa de valer.
      await queryClient.invalidateQueries({ queryKey: ["sgd", "diarias", "simulacao"] });
      showToast("Parâmetros de contagem atualizados.", "success");
    },
    onError: (e) => setErro(e instanceof ApiError ? e.message : "Não foi possível salvar os parâmetros."),
  });

  return (
    <form
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface px-5 py-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!adicionalSemValor) salvar.mutate();
      }}
      data-testid="parametros-diarias"
    >
      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 text-sm font-medium text-text">Regras de contagem</legend>
        {REGRAS_DE_CONTAGEM.map(({ chave, rotulo, ajuda }) => {
          const semEfeito = meiasSemEfeito && chave !== "regra_inteira_por_pernoite";
          return (
            <label key={chave} className="flex cursor-pointer items-start gap-2 text-sm text-text">
              <input
                type="checkbox"
                className="mt-0.5 accent-primary"
                checked={form[chave]}
                disabled={salvar.isPending}
                onChange={(e) => setForm((f) => ({ ...f, [chave]: e.target.checked }))}
                data-testid={`parametro-${chave}`}
              />
              <span>
                {rotulo}
                <span className="block text-xs text-text-muted">
                  {semEfeito ? "Sem efeito enquanto a diária inteira por pernoite estiver desligada." : ajuda}
                </span>
              </span>
            </label>
          );
        })}
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 text-sm font-medium text-text">Adicional de embarque e desembarque</legend>
        <label className="flex cursor-pointer items-start gap-2 text-sm text-text">
          <input
            type="checkbox"
            className="mt-0.5 accent-primary"
            checked={form.adicional_embarque_ativo}
            disabled={salvar.isPending}
            onChange={(e) => setForm((f) => ({ ...f, adicional_embarque_ativo: e.target.checked }))}
            data-testid="parametro-adicional_embarque_ativo"
          />
          <span>
            Somar o adicional ao total de cada solicitação de diária
            <span className="block text-xs text-text-muted">Desligado, o valor abaixo fica guardado e não entra no total.</span>
          </span>
        </label>
        <div className="max-w-xs">
          <Input
            id="parametro-adicional-valor"
            label="Valor do adicional"
            inputMode="numeric"
            placeholder="R$ 0,00"
            value={adicional}
            onChange={(e) => setAdicional(formatMoneyInput(e.target.value))}
            disabled={salvar.isPending}
            error={adicionalSemValor ? "Informe o valor do adicional para ligá-lo." : undefined}
          />
        </div>
      </fieldset>

      {erro && (
        <p role="alert" className="text-sm text-error-text" data-testid="parametros-diarias-erro">
          {erro}
        </p>
      )}

      <div className="flex justify-end">
        <Button
          type="submit"
          disabled={!mudou || adicionalSemValor}
          loading={salvar.isPending}
          data-testid="parametros-diarias-salvar"
        >
          Salvar parâmetros
        </Button>
      </div>
    </form>
  );
}
