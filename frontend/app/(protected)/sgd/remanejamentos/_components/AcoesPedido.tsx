"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/app/components/ui/Button/Button";
import { ConfirmationDrawer } from "@/app/components/ui/ConfirmationDrawer/ConfirmationDrawer";
import { Input } from "@/app/components/ui/Input/Input";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { ApiError } from "@/app/lib/api";
import { canDecidirRemanejamento, canEmitirParecerRemanejamento } from "@/app/lib/auth/roles";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import {
  decidirPedido,
  devolverPedido,
  editarPedido,
  emitirParecer,
  erroDoCampo,
  reenviarPedido,
  type PedidoRecursoExtra,
} from "@/app/lib/remanejamentos";
import { OrigemAlocacao } from "./OrigemAlocacao";

export type Desfecho = { tipo: "sucesso" | "info"; texto: string };

type Drawer = "parecer" | "devolver" | "aprovar" | "parcial" | "recusar" | null;

function mensagemDe(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return "Não foi possível registrar a ação. Tente novamente.";
}

/**
 * Ações sobre o pedido de recurso extra (#321), pelo perfil E pelo status —
 * espelhando `RemanejamentoViewSet`:
 *
 * - Articulador Estadual, em Submetida: Emitir parecer · Devolver
 * - UGP, em Com parecer: Aprovar · Aprovar parcialmente · Recusar
 * - Solicitante, em Devolvida: ajustar a justificativa e reenviar
 * - Super Admin: as do Articulador e as da UGP
 *
 * Toda decisão passa pelo `ConfirmationDrawer`, com justificativa obrigatória
 * — o backend exige nas três decisões da UGP.
 */
export function AcoesPedido({
  pedido,
  onDecidido,
  onIniciar,
}: {
  pedido: PedidoRecursoExtra;
  onDecidido: (desfecho: Desfecho) => void;
  /** Uma nova ação começou: a mensagem da anterior deixa de valer. */
  onIniciar: () => void;
}) {
  const { data: session } = useSession();
  const user = session?.user;
  const queryClient = useQueryClient();

  const [drawer, setDrawer] = useState<Drawer>(null);
  const [valorParcial, setValorParcial] = useState("");
  // A aprovação pede a alocação de origem só quando o backend diz que o pool
  // territorial não cobre a demanda (erro em `origem_allocation`).
  const [precisaOrigem, setPrecisaOrigem] = useState(false);
  const [origem, setOrigem] = useState("");
  const [justificativaReenvio, setJustificativaReenvio] = useState(pedido.justificativa);
  const [reenviando, setReenviando] = useState(false);
  const [erroReenvio, setErroReenvio] = useState<string | null>(null);

  const podeParecer = canEmitirParecerRemanejamento(user) && pedido.status === "submetida";
  const podeDecidir = canDecidirRemanejamento(user) && pedido.status === "com_parecer";
  const podeReenviar = String(user?.id) === String(pedido.user) && pedido.status === "devolvida";

  if (!podeParecer && !podeDecidir && !podeReenviar) return null;

  function abrir(qual: Drawer) {
    onIniciar();
    setValorParcial("");
    setPrecisaOrigem(false);
    setOrigem("");
    setDrawer(qual);
  }

  /** A resposta da ação já é o pedido atualizado; listas e demandas recarregam em segundo plano. */
  function aplicar(atualizado: PedidoRecursoExtra, desfecho: Desfecho) {
    queryClient.setQueryData(qk.remanejamentos.detalhe(atualizado.id), atualizado);
    void queryClient.invalidateQueries({ queryKey: qk.remanejamentos.all });
    // Aprovar eleva o limite individual: o saldo das demandas muda.
    void queryClient.invalidateQueries({ queryKey: qk.demandas.all });
    setDrawer(null);
    onDecidido(desfecho);
  }

  async function confirmar(acao: () => Promise<PedidoRecursoExtra>, desfecho: Desfecho) {
    onIniciar();
    let atualizado: PedidoRecursoExtra;
    try {
      atualizado = await acao();
    } catch (e) {
      if (erroDoCampo(e, "origem_allocation")) setPrecisaOrigem(true);
      throw new Error(mensagemDe(e));
    }
    aplicar(atualizado, desfecho);
  }

  const origemId = origem ? Number(origem) : null;
  const campoOrigem = precisaOrigem && (
    <OrigemAlocacao pedido={pedido} value={origem} onChange={setOrigem} />
  );
  const liberadaDemanda =
    "O limite individual do solicitante foi elevado: a demanda já pode ser submetida de novo. O solicitante foi notificado.";

  return (
    <section className="flex flex-col gap-3 border-t border-border pt-4" data-testid="pedido-acoes">
      {podeReenviar && (
        <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-5">
          <h2 className="text-sm font-semibold text-text">Ajustar e reenviar</h2>
          <Textarea
            id={`reenvio-${pedido.id}`}
            label="Justificativa"
            required
            rows={4}
            value={justificativaReenvio}
            onChange={(e) => {
              setJustificativaReenvio(e.target.value);
              setErroReenvio(null);
            }}
            helperText="Responda ao motivo da devolução. O pedido volta ao Articulador."
          />
          {erroReenvio && (
            <p role="alert" className="text-sm text-error-text">
              {erroReenvio}
            </p>
          )}
          <div className="flex justify-end">
            <Button
              loading={reenviando}
              onClick={async () => {
                const texto = justificativaReenvio.trim();
                if (!texto) {
                  setErroReenvio("A justificativa é obrigatória.");
                  return;
                }
                onIniciar();
                setReenviando(true);
                setErroReenvio(null);
                try {
                  if (texto !== pedido.justificativa) await editarPedido(pedido.id, { justificativa: texto });
                  aplicar(await reenviarPedido(pedido.id), {
                    tipo: "sucesso",
                    texto: "Pedido reenviado ao Articulador Estadual.",
                  });
                } catch (e) {
                  setErroReenvio(mensagemDe(e));
                } finally {
                  setReenviando(false);
                }
              }}
              data-testid="acao-reenviar"
            >
              Reenviar pedido
            </Button>
          </div>
        </div>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        {podeParecer && (
          <>
            <Button variant="secondary" onClick={() => abrir("devolver")} data-testid="acao-devolver">
              Devolver ao solicitante
            </Button>
            <Button onClick={() => abrir("parecer")} data-testid="acao-parecer">
              Emitir parecer
            </Button>
          </>
        )}
        {podeDecidir && (
          <>
            <Button variant="danger" onClick={() => abrir("recusar")} data-testid="acao-recusar">
              Recusar
            </Button>
            <Button variant="secondary" onClick={() => abrir("parcial")} data-testid="acao-parcial">
              Aprovar parcialmente
            </Button>
            <Button onClick={() => abrir("aprovar")} data-testid="acao-aprovar">
              Aprovar
            </Button>
          </>
        )}
      </div>

      <ConfirmationDrawer
        open={drawer === "parecer"}
        tom="confirmacao"
        title="Emitir parecer"
        description={
          <p>
            O pedido de {formatCurrencyBRL(pedido.valor_solicitado)} em {pedido.rubrica_nome} segue
            para a decisão da UGP com o seu parecer.
          </p>
        }
        confirmLabel="Emitir parecer"
        keepLabel="Voltar"
        justificativaLabel="Parecer"
        onClose={() => setDrawer(null)}
        onConfirm={(texto) =>
          confirmar(() => emitirParecer(pedido.id, texto), {
            tipo: "sucesso",
            texto: "Parecer emitido. O pedido segue para a decisão da UGP.",
          })
        }
        data-testid="parecer-drawer"
      />

      <ConfirmationDrawer
        open={drawer === "devolver"}
        title="Devolver pedido"
        description={
          <p>
            O pedido volta ao solicitante, que pode ajustá-lo e reenviar. Ele recebe o motivo da
            devolução.
          </p>
        }
        confirmLabel="Devolver pedido"
        keepLabel="Voltar"
        justificativaLabel="Motivo da devolução"
        onClose={() => setDrawer(null)}
        onConfirm={(texto) =>
          confirmar(() => devolverPedido(pedido.id, texto), {
            tipo: "info",
            texto: "Pedido devolvido ao solicitante.",
          })
        }
        data-testid="devolver-drawer"
      />

      <ConfirmationDrawer
        open={drawer === "aprovar"}
        tom="confirmacao"
        title="Aprovar recurso extra"
        description={
          <>
            <p className="font-medium text-text">
              O limite individual de {pedido.solicitante_nome} em {pedido.rubrica_nome} sobe{" "}
              {formatCurrencyBRL(pedido.valor_solicitado)}.
            </p>
            <p className="mt-1">
              A demanda não é submetida sozinha: o solicitante é notificado e submete de novo.
            </p>
          </>
        }
        confirmLabel="Aprovar recurso extra"
        keepLabel="Voltar"
        justificativaLabel="Justificativa da aprovação"
        onClose={() => setDrawer(null)}
        onConfirm={(texto) =>
          confirmar(
            () =>
              decidirPedido(pedido.id, {
                decisao: "aprovar",
                justificativa: texto,
                origemAllocation: origemId,
              }),
            { tipo: "sucesso", texto: `Recurso extra aprovado. ${liberadaDemanda}` },
          )
        }
        data-testid="aprovar-drawer"
      >
        {campoOrigem}
      </ConfirmationDrawer>

      <ConfirmationDrawer
        open={drawer === "parcial"}
        tom="confirmacao"
        title="Aprovar parcialmente"
        description={
          <p>
            O limite individual de {pedido.solicitante_nome} sobe o valor informado, menor que os{" "}
            {formatCurrencyBRL(pedido.valor_solicitado)} pedidos. Se não cobrir o que a demanda
            precisa, ela continua bloqueada.
          </p>
        }
        confirmLabel="Aprovar parcialmente"
        keepLabel="Voltar"
        justificativaLabel="Justificativa da aprovação parcial"
        onClose={() => setDrawer(null)}
        onConfirm={(texto) => {
          if (!valorParcial) {
            return Promise.reject(new Error("Informe o valor aprovado."));
          }
          return confirmar(
            () =>
              decidirPedido(pedido.id, {
                decisao: "aprovar_parcialmente",
                justificativa: texto,
                valorAprovado: valorParcial,
                origemAllocation: origemId,
              }),
            {
              tipo: "sucesso",
              texto: "Recurso extra aprovado parcialmente. O solicitante foi notificado.",
            },
          );
        }}
        data-testid="parcial-drawer"
      >
        <Input
          id={`parcial-${pedido.id}`}
          label="Valor aprovado"
          type="number"
          min={0}
          step="0.01"
          inputMode="decimal"
          required
          value={valorParcial}
          onChange={(e) => setValorParcial(e.target.value)}
          helperText={`Solicitado: ${formatCurrencyBRL(pedido.valor_solicitado)}`}
          data-testid="parcial-valor"
        />
        {campoOrigem}
      </ConfirmationDrawer>

      <ConfirmationDrawer
        open={drawer === "recusar"}
        title="Recusar recurso extra"
        description={
          <>
            <p className="font-medium text-text">A recusa é definitiva.</p>
            <p className="mt-1">
              O limite individual não muda e a demanda continua bloqueada. O solicitante recebe a
              justificativa.
            </p>
          </>
        }
        confirmLabel="Recusar pedido"
        keepLabel="Voltar"
        justificativaLabel="Justificativa da recusa"
        onClose={() => setDrawer(null)}
        onConfirm={(texto) =>
          confirmar(() => decidirPedido(pedido.id, { decisao: "recusar", justificativa: texto }), {
            tipo: "info",
            texto: "Pedido recusado. A demanda continua bloqueada e o solicitante foi notificado.",
          })
        }
        data-testid="recusar-drawer"
      />
    </section>
  );
}
