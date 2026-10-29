"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Info } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import {
  camposVisiveis,
  CONFIG_POR_TIPO,
  isTipoSolicitacao,
  montarCamposJson,
  validarCampos,
  valoresDoCamposJson,
  type TipoSolicitacao,
  type ValoresCampos,
} from "@/app/lib/camposSolicitacao";
import type { Demanda, SolicitacaoDemanda } from "@/app/lib/demandas";
import { formatMoneyInput, moneyOrNull } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import {
  atualizarSolicitacao,
  COTACOES_MINIMAS,
  criarSolicitacao,
  type SolicitacaoPayload,
} from "@/app/lib/solicitacoes";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";
import { CampoDinamico } from "./CampoDinamico";
import { SaldoSolicitacao } from "./SaldoSolicitacao";
import { SimulacaoDiarias, useSimulacaoDiarias } from "./SimulacaoDiarias";

const CAMPO_VALOR = "valor_estimado";

/**
 * Formulário de uma solicitação de recurso (#295, SGD-RF04/RF05): os campos
 * mudam com o tipo, e o saldo das duas travas aparece antes de salvar.
 *
 * Salvar grava a solicitação na demanda (Rascunho ou Devolvida) sem reservar
 * saldo — a reserva é da submissão. Uma solicitação salva troca de tipo só
 * removendo e criando outra: o tipo define a rubrica.
 */
export function SolicitacaoForm({
  demanda,
  solicitacao,
  onClose,
  onSalvo,
}: {
  demanda: Demanda;
  /** Null: nova solicitação. */
  solicitacao: SolicitacaoDemanda | null;
  onClose: () => void;
  onSalvo: (salva: SolicitacaoDemanda, nova: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const choices = useSgpChoices();

  const tipoInicial = solicitacao && isTipoSolicitacao(solicitacao.tipo) ? solicitacao.tipo : "";
  const [tipo, setTipo] = useState<TipoSolicitacao | "">(tipoInicial);
  const [valores, setValores] = useState<ValoresCampos>(() =>
    tipoInicial && solicitacao ? valoresDoCamposJson(tipoInicial, solicitacao.campos_json) : {},
  );
  const [valorEstimado, setValorEstimado] = useState(() =>
    solicitacao ? formatMoneyInput(solicitacao.valor_estimado) : "",
  );
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  const config = tipo ? CONFIG_POR_TIPO[tipo] : null;
  const diarias = useSimulacaoDiarias(
    tipo === "diaria" ? (valores.municipio_destino_id ?? "") : "",
    valores.data_inicio ?? "",
    valores.data_fim ?? "",
  );

  // O valor que o saldo confere: o digitado, ou, na diária, o que o backend calcula.
  const valorParaSaldo = config?.valorDigitado
    ? (moneyOrNull(valorEstimado) ?? "0")
    : (diarias.simulacao.data?.valor_total ?? solicitacao?.valor_estimado ?? "0");

  function mudarCampo(chave: string, valor: string) {
    setValores((prev) => ({ ...prev, [chave]: valor }));
    setErros((prev) => {
      const next = { ...prev };
      delete next[chave];
      return next;
    });
  }

  function mudarTipo(novo: string) {
    if (!isTipoSolicitacao(novo)) return;
    setTipo(novo);
    setValores({});
    setErros({});
    setErroGeral(null);
  }

  async function salvar() {
    if (!tipo || !config) {
      setErros({ tipo: "Escolha o tipo da solicitação." });
      return;
    }
    const e = validarCampos(tipo, valores);
    const valor = moneyOrNull(valorEstimado);
    if (config.valorDigitado && !(valor && Number(valor) > 0)) {
      e[CAMPO_VALOR] = "Informe o valor estimado.";
    }
    setErros(e);
    setErroGeral(null);
    if (Object.keys(e).length > 0) return;

    const payload: SolicitacaoPayload = { tipo, campos_json: montarCamposJson(tipo, valores) };
    if (config.valorDigitado && valor) payload.valor_estimado = valor;

    setSalvando(true);
    try {
      const salva = solicitacao
        ? await atualizarSolicitacao(demanda.id, solicitacao.id, payload)
        : await criarSolicitacao(demanda.id, payload);
      await queryClient.invalidateQueries({ queryKey: qk.demandas.all });
      onSalvo(salva, solicitacao === null);
    } catch (err) {
      if (!(err instanceof ApiError)) {
        setErroGeral("Não foi possível salvar a solicitação. Tente novamente.");
        return;
      }
      // Erro de um campo à vista vai para o campo; o resto, para o topo.
      const visiveis = new Set([...camposVisiveis(tipo, valores).map((c) => c.chave), CAMPO_VALOR]);
      const porCampo: Record<string, string> = {};
      const soltos: string[] = [];
      for (const fe of err.fieldErrors ?? []) {
        if (visiveis.has(fe.field)) porCampo[fe.field] = fe.message;
        else soltos.push(fe.message);
      }
      setErros(porCampo);
      if (soltos.length > 0 || Object.keys(porCampo).length === 0) {
        setErroGeral(soltos.length > 0 ? soltos.join(" ") : err.message);
      }
    } finally {
      setSalvando(false);
    }
  }

  const rodape = (
    <div className="flex items-center justify-end gap-2">
      <Button variant="secondary" onClick={onClose} disabled={salvando}>
        Cancelar
      </Button>
      <Button onClick={salvar} loading={salvando} disabled={!tipo} data-testid="solicitacao-salvar">
        Salvar solicitação
      </Button>
    </div>
  );

  return (
    <SlideOver
      open
      onClose={salvando ? () => {} : onClose}
      title={solicitacao ? `Editar solicitação — ${solicitacao.tipo_display}` : "Nova solicitação de recurso"}
      footer={rodape}
    >
      <div className="flex flex-col gap-5 px-4 py-4" data-testid="solicitacao-form">
        {!solicitacao && (
          <Select
            id="solicitacao-tipo"
            label="Tipo de solicitação"
            required
            options={choices.solicitacao_tipo.filter((op) => isTipoSolicitacao(op.value))}
            value={tipo}
            onChange={mudarTipo}
            error={erros.tipo}
            name="tipo"
          />
        )}

        {tipo && config && (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              {camposVisiveis(tipo, valores).map((campo) => (
                <div key={campo.chave} className={campo.largo ? "sm:col-span-2" : undefined}>
                  <CampoDinamico
                    campo={campo}
                    valor={valores[campo.chave] ?? ""}
                    onChange={(v) => mudarCampo(campo.chave, v)}
                    error={erros[campo.chave]}
                  />
                </div>
              ))}
            </div>

            {config.valorDigitado ? (
              <Input
                id="solicitacao-valor"
                label="Valor estimado"
                required
                inputMode="numeric"
                value={valorEstimado}
                onChange={(ev) => {
                  setValorEstimado(formatMoneyInput(ev.target.value));
                  mudarCampo(CAMPO_VALOR, "");
                }}
                error={erros[CAMPO_VALOR]}
              />
            ) : (
              <SimulacaoDiarias {...diarias} />
            )}

            {tipo === "equipamento" && (
              <p className="flex items-start gap-2 rounded-md border border-info-text bg-info-bg px-3 py-2.5 text-sm text-info-text">
                <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                A submissão exige ao menos {COTACOES_MINIMAS} cotações em PDF, de fornecedores distintos.
                Anexe-as em “Documentos” na página da demanda.
              </p>
            )}

            <SaldoSolicitacao
              atividadeId={demanda.activity}
              tipo={tipo}
              valor={valorParaSaldo}
              devolvida={demanda.status === "devolvida"}
            />
          </>
        )}

        {erroGeral && (
          <p
            role="alert"
            className="flex items-start gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
            data-testid="solicitacao-erro"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            {erroGeral}
          </p>
        )}
      </div>
    </SlideOver>
  );
}
