"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { ApiError } from "@/app/lib/api";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import {
  solicitarRecursoExtra,
  type BloqueioRecursoExtra,
  type PedidoRecursoExtra,
} from "@/app/lib/remanejamentos";

type Etapa = "preencher" | "confirmar" | "enviado";

/**
 * Fluxo guiado "Solicitar recurso extra" (#321 · SGD §4.1): o atalho da
 * demanda que a submissão barrou no limite individual.
 *
 * Quem abre é a tela de submissão da #295: ela recebe o 400, passa por
 * `bloqueioDeRecursoExtra` e, havendo bloqueio, abre este painel com ele. Aqui
 * não há botão de submeter — isso é da #295.
 *
 * Três passos: justificativa → revisão → pedido enviado. O valor não é
 * calculado na tela: sem `valor_solicitado`, o backend assume o que falta no
 * limite individual da rubrica inteira, e o valor registrado aparece no passo
 * final. O disponível e o solicitado do bloqueio são só da solicitação
 * barrada; o que falta na rubrica vem em `valor_faltante`, quando o backend
 * o expuser (pendencias-backend-sprint-10.md, item 23).
 */
export function SolicitarRecursoExtra({
  open,
  demanda,
  bloqueio,
  onClose,
  onEnviado,
}: {
  open: boolean;
  demanda: { id: number; titulo: string };
  bloqueio: BloqueioRecursoExtra;
  onClose: () => void;
  onEnviado?: (pedido: PedidoRecursoExtra) => void;
}) {
  const campoId = useId();
  const queryClient = useQueryClient();
  const [etapa, setEtapa] = useState<Etapa>("preencher");
  const [justificativa, setJustificativa] = useState("");
  const [erroCampo, setErroCampo] = useState<string | null>(null);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [pedido, setPedido] = useState<PedidoRecursoExtra | null>(null);

  function fechar() {
    if (enviando) return;
    setEtapa("preencher");
    setJustificativa("");
    setErroCampo(null);
    setErroGeral(null);
    setPedido(null);
    onClose();
  }

  function revisar() {
    if (!justificativa.trim()) {
      setErroCampo("A justificativa é obrigatória.");
      return;
    }
    setErroGeral(null);
    setEtapa("confirmar");
  }

  async function enviar() {
    setEnviando(true);
    setErroGeral(null);
    try {
      const criado = await solicitarRecursoExtra(demanda.id, {
        rubrica: bloqueio.rubrica.slug,
        justificativa: justificativa.trim(),
      });
      setPedido(criado);
      setEtapa("enviado");
      void queryClient.invalidateQueries({ queryKey: qk.remanejamentos.all });
      onEnviado?.(criado);
    } catch (e) {
      setErroGeral(e instanceof ApiError ? e.message : "Não foi possível enviar o pedido. Tente novamente.");
    } finally {
      setEnviando(false);
    }
  }

  const resumo = (
    <DefinitionList
      items={[
        { label: "Demanda", value: demanda.titulo },
        { label: "Rubrica", value: bloqueio.rubrica.nome },
        {
          label: "Valor",
          value:
            etapa === "enviado" && pedido
              ? formatCurrencyBRL(pedido.valor_solicitado)
              : bloqueio.valorFaltante !== null
                ? formatCurrencyBRL(bloqueio.valorFaltante)
                : "O que falta no seu limite individual, calculado pelo sistema ao registrar o pedido",
        },
        ...(etapa !== "preencher" ? [{ label: "Justificativa", value: justificativa.trim() }] : []),
      ]}
    />
  );

  const rodape =
    etapa === "preencher" ? (
      <div className="flex items-center justify-end gap-2">
        <Button variant="secondary" onClick={fechar}>
          Cancelar
        </Button>
        <Button onClick={revisar} data-testid="recurso-extra-revisar">
          Revisar pedido
        </Button>
      </div>
    ) : etapa === "confirmar" ? (
      <div className="flex items-center justify-end gap-2">
        <Button variant="secondary" onClick={() => setEtapa("preencher")} disabled={enviando}>
          Voltar
        </Button>
        <Button onClick={enviar} loading={enviando} data-testid="recurso-extra-enviar">
          Enviar pedido
        </Button>
      </div>
    ) : (
      <div className="flex items-center justify-end">
        <Button onClick={fechar}>Fechar</Button>
      </div>
    );

  return (
    <SlideOver open={open} onClose={fechar} title="Solicitar recurso extra" footer={rodape}>
      <div className="flex flex-col gap-5 px-4 py-4" data-testid="recurso-extra-drawer">
        {etapa === "enviado" && pedido ? (
          <>
            <p
              role="status"
              className="flex items-start gap-2 rounded-md border border-success-text bg-success-bg px-3 py-2.5 text-sm text-success-text"
              data-testid="recurso-extra-enviado"
            >
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              Pedido enviado. O Articulador Estadual emite o parecer e a UGP decide; você é notificado
              da decisão. Aprovado o pedido, submeta a demanda de novo.
            </p>
            {resumo}
            <Link
              href={`/sgd/remanejamentos/${pedido.id}`}
              className="text-sm text-primary hover:underline"
            >
              Acompanhar o pedido #{pedido.id}
            </Link>
          </>
        ) : (
          <>
            <p
              className="flex items-start gap-2 rounded-md border border-warning-text bg-warning-bg px-3 py-2.5 text-sm text-warning-text"
              data-testid="recurso-extra-bloqueio"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span className="tabular-nums">
                Limite individual insuficiente: {formatCurrencyBRL(bloqueio.disponivel)} disponível,{" "}
                {formatCurrencyBRL(bloqueio.solicitado)} solicitado.
              </span>
            </p>

            {etapa === "confirmar" && (
              <p className="text-sm font-medium text-text">Confira o pedido antes de enviar.</p>
            )}
            {resumo}

            {etapa === "preencher" && (
              <Textarea
                id={campoId}
                label="Justificativa"
                required
                rows={4}
                value={justificativa}
                onChange={(e) => {
                  setJustificativa(e.target.value);
                  setErroCampo(null);
                }}
                helperText="Por que a demanda precisa de recurso além do seu limite. O Articulador e a UGP leem este texto."
                error={erroCampo ?? undefined}
              />
            )}

            {erroGeral && (
              <p role="alert" className="text-sm text-error-text" data-testid="recurso-extra-erro">
                {erroGeral}
              </p>
            )}
          </>
        )}
      </div>
    </SlideOver>
  );
}
