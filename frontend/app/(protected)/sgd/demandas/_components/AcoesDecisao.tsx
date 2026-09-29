"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/app/components/ui/Button/Button";
import { ConfirmationDrawer } from "@/app/components/ui/ConfirmationDrawer/ConfirmationDrawer";
import { Input } from "@/app/components/ui/Input/Input";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { ApiError } from "@/app/lib/api";
import { perfisDecisoresSgd } from "@/app/lib/auth/roles";
import {
  atenderDemanda,
  autorizarDemanda,
  concluirDemanda,
  devolverDemanda,
  preAutorizarDemanda,
  recusarDemanda,
  type Demanda,
} from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import { PreviewImpacto } from "./PreviewImpacto";

export type Desfecho = { tipo: "sucesso" | "info"; texto: string };

type Modo = "inicio" | "pre-autorizar" | "devolver" | "autorizar" | "ajustar" | "concluir";

function mensagemDe(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return "Não foi possível registrar a decisão. Tente novamente.";
}

/** Decimal da API ("1200.00") como valor de input. */
const paraInput = (v: string | null) => (v === null ? "" : String(Number(v)));

/**
 * Rodapé de decisão do painel (#296). As ações aparecem pelo perfil E pelo
 * status — espelhando `DemandApprovalMixin`:
 *
 * - Articulador Estadual, em Submetida: Pré-autorizar · Devolver para revisão
 * - UGP, em Pré-autorizada: Autorizar · Autorizar com valor ajustado · Recusar
 * - FGD, em Autorizada: Iniciar atendimento; em Em atendimento: Concluir
 *
 * Toda decisão que reserva recurso passa por uma confirmação com o preview de
 * impacto no saldo. O backend continua sendo quem autoriza — um 403/400 volta
 * como mensagem aqui.
 */
export function AcoesDecisao({
  demanda,
  onDecidido,
  onIniciar,
}: {
  demanda: Demanda;
  onDecidido: (desfecho: Desfecho) => void;
  /** Uma nova ação começou: a mensagem da decisão anterior deixa de valer. */
  onIniciar: () => void;
}) {
  const { data: session } = useSession();
  const perfis = perfisDecisoresSgd(session?.user);
  const queryClient = useQueryClient();

  const [modo, setModo] = useState<Modo>("inicio");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [justificativa, setJustificativa] = useState("");
  const [erroJustificativa, setErroJustificativa] = useState<string | null>(null);
  const [recusando, setRecusando] = useState(false);
  const [valores, setValores] = useState<Record<number, string>>({});

  const { status, solicitacoes } = demanda;
  const podeArticulador = perfis.includes("articulador-estadual") && status === "submetida";
  const podeUgp = perfis.includes("ugp") && status === "pre_autorizada";
  const podeAtender = perfis.includes("fgd") && status === "autorizada";
  const podeConcluir = perfis.includes("fgd") && status === "em_atendimento";

  if (!podeArticulador && !podeUgp && !podeAtender && !podeConcluir) return null;

  function abrir(novo: Modo) {
    onIniciar();
    setErro(null);
    setErroJustificativa(null);
    setJustificativa("");
    if (novo === "ajustar") {
      setValores(Object.fromEntries(solicitacoes.map((s) => [s.id, paraInput(s.valor_estimado)])));
    } else if (novo === "concluir") {
      setValores(
        Object.fromEntries(
          solicitacoes.map((s) => [s.id, paraInput(s.valor_autorizado ?? s.valor_estimado)]),
        ),
      );
    }
    setModo(novo);
  }

  /**
   * A tela troca de estado com a demanda que a PRÓPRIA resposta da decisão
   * devolve — não espera recarregar nada. Filas, contagens e listas são
   * invalidadas em segundo plano: esperar por elas travava o painel por
   * segundos, e nesse meio-tempo o próximo botão (ex.: Concluir, logo após
   * Iniciar atendimento) aparecia, abria e era desfeito sozinho.
   */
  function aplicarDecisao(atualizada: Demanda, desfecho: Desfecho) {
    queryClient.setQueryData(qk.demandas.detalhe(atualizada.id), atualizada);
    void queryClient.invalidateQueries({ queryKey: qk.demandas.all });
    setModo("inicio");
    onDecidido(desfecho);
  }

  async function executar(acao: () => Promise<Demanda>, desfecho: Desfecho) {
    onIniciar();
    setEnviando(true);
    setErro(null);
    try {
      aplicarDecisao(await acao(), desfecho);
    } catch (e) {
      setErro(mensagemDe(e));
    } finally {
      setEnviando(false);
    }
  }

  const erroBox = erro && (
    <p role="alert" className="text-sm text-error-text" data-testid="decisao-erro">
      {erro}
    </p>
  );

  const voltar = (
    <Button variant="ghost" onClick={() => setModo("inicio")} disabled={enviando}>
      Voltar
    </Button>
  );

  /** Preview de cada solicitação com o valor que a decisão vai reservar. */
  const previews = (valorDe: (id: number, estimado: string) => string) => (
    <div className="flex flex-col gap-2" data-testid="decisao-preview">
      <p className="text-xs font-medium text-text">Impacto no saldo da rubrica</p>
      {solicitacoes.map((s) => (
        <PreviewImpacto
          key={s.id}
          demandaId={demanda.id}
          solicitacao={s}
          valor={valorDe(s.id, paraInput(s.valor_estimado))}
        />
      ))}
    </div>
  );

  let conteudo: React.ReactNode;

  if (modo === "pre-autorizar") {
    conteudo = (
      <>
        {previews((_, estimado) => estimado)}
        {erroBox}
        <div className="flex justify-end gap-2">
          {voltar}
          <Button
            loading={enviando}
            onClick={() =>
              executar(() => preAutorizarDemanda(demanda.id), {
                tipo: "sucesso",
                texto: "Demanda pré-autorizada. Ela segue para a autorização da UGP.",
              })
            }
            data-testid="decisao-confirmar"
          >
            Confirmar pré-autorização
          </Button>
        </div>
      </>
    );
  } else if (modo === "devolver") {
    conteudo = (
      <>
        <Textarea
          id={`devolver-${demanda.id}`}
          label="Motivo da devolução"
          required
          rows={3}
          value={justificativa}
          onChange={(e) => {
            setJustificativa(e.target.value);
            setErroJustificativa(null);
          }}
          helperText="O solicitante recebe este texto para corrigir a demanda."
          error={erroJustificativa ?? undefined}
        />
        {erroBox}
        <div className="flex justify-end gap-2">
          {voltar}
          <Button
            loading={enviando}
            onClick={() => {
              const texto = justificativa.trim();
              if (!texto) {
                setErroJustificativa("Informe o motivo da devolução.");
                return;
              }
              void executar(() => devolverDemanda(demanda.id, texto), {
                tipo: "info",
                texto: "Demanda devolvida para revisão. O solicitante foi notificado.",
              });
            }}
            data-testid="decisao-confirmar"
          >
            Confirmar devolução
          </Button>
        </div>
      </>
    );
  } else if (modo === "autorizar") {
    conteudo = (
      <>
        {previews((_, estimado) => estimado)}
        {erroBox}
        <div className="flex justify-end gap-2">
          {voltar}
          <Button
            loading={enviando}
            onClick={() =>
              executar(() => autorizarDemanda(demanda.id), {
                tipo: "sucesso",
                texto: "Demanda autorizada. Ela segue para o atendimento da FGD.",
              })
            }
            data-testid="decisao-confirmar"
          >
            Confirmar autorização
          </Button>
        </div>
      </>
    );
  } else if (modo === "ajustar") {
    conteudo = (
      <>
        {solicitacoes.map((s) => (
          <Input
            key={s.id}
            id={`ajuste-${s.id}`}
            label={`Valor autorizado — ${s.tipo_display}`}
            type="number"
            min={0}
            step="0.01"
            inputMode="decimal"
            value={valores[s.id] ?? ""}
            onChange={(e) => setValores((v) => ({ ...v, [s.id]: e.target.value }))}
            helperText={`Pedido: ${formatCurrencyBRL(s.valor_estimado)}`}
          />
        ))}
        {previews((id) => valores[id] ?? "")}
        {erroBox}
        <div className="flex justify-end gap-2">
          {voltar}
          <Button
            loading={enviando}
            onClick={() => {
              // Só vai no `ajustes` o que mudou: o resto é autorizado como pedido.
              const ajustes: Record<number, string> = {};
              for (const s of solicitacoes) {
                const v = valores[s.id];
                if (v !== "" && Number(v) !== Number(s.valor_estimado)) ajustes[s.id] = v;
              }
              void executar(() => autorizarDemanda(demanda.id, ajustes), {
                tipo: "sucesso",
                texto: "Demanda autorizada com o valor ajustado.",
              });
            }}
            data-testid="decisao-confirmar"
          >
            Autorizar com estes valores
          </Button>
        </div>
      </>
    );
  } else if (modo === "concluir") {
    conteudo = (
      <>
        {solicitacoes.map((s) => (
          <Input
            key={s.id}
            id={`pago-${s.id}`}
            label={`Valor pago — ${s.tipo_display}`}
            type="number"
            min={0}
            step="0.01"
            inputMode="decimal"
            required
            value={valores[s.id] ?? ""}
            onChange={(e) => setValores((v) => ({ ...v, [s.id]: e.target.value }))}
            helperText={`Autorizado: ${formatCurrencyBRL(s.valor_autorizado ?? s.valor_estimado)}`}
          />
        ))}
        {erroBox}
        <div className="flex justify-end gap-2">
          {voltar}
          <Button
            loading={enviando}
            onClick={() =>
              executar(() => concluirDemanda(demanda.id, valores), {
                tipo: "sucesso",
                texto: "Demanda concluída com os valores pagos registrados.",
              })
            }
            data-testid="decisao-confirmar"
          >
            Confirmar conclusão
          </Button>
        </div>
      </>
    );
  } else if (enviando) {
    conteudo = (
      <p role="status" className="text-sm text-text-muted" data-testid="decisao-enviando">
        Registrando a decisão…
      </p>
    );
  } else {
    conteudo = (
      <>
        {erroBox}
        <div className="flex flex-wrap justify-end gap-2">
          {podeArticulador && (
            <>
              <Button variant="secondary" onClick={() => abrir("devolver")} data-testid="acao-devolver">
                Devolver para revisão
              </Button>
              <Button onClick={() => abrir("pre-autorizar")} data-testid="acao-pre-autorizar">
                Pré-autorizar
              </Button>
            </>
          )}
          {podeUgp && (
            <>
              <Button variant="danger" onClick={() => setRecusando(true)} data-testid="acao-recusar">
                Recusar
              </Button>
              <Button variant="secondary" onClick={() => abrir("ajustar")} data-testid="acao-ajustar">
                Autorizar com valor ajustado
              </Button>
              <Button onClick={() => abrir("autorizar")} data-testid="acao-autorizar">
                Autorizar
              </Button>
            </>
          )}
          {podeAtender && (
            <Button
              loading={enviando}
              onClick={() =>
                executar(() => atenderDemanda(demanda.id), {
                  tipo: "sucesso",
                  texto: "Atendimento iniciado.",
                })
              }
              data-testid="acao-atender"
            >
              Iniciar atendimento
            </Button>
          )}
          {podeConcluir && (
            <Button onClick={() => abrir("concluir")} data-testid="acao-concluir">
              Concluir
            </Button>
          )}
        </div>
      </>
    );
  }

  return (
    <div className="flex flex-col gap-3 border-t border-border pt-4" data-testid="decisao-rodape">
      {conteudo}

      <ConfirmationDrawer
        open={recusando}
        title="Recusar demanda"
        description={
          <>
            <p className="font-medium text-text">A recusa é definitiva.</p>
            <p className="mt-1">
              A demanda “{demanda.titulo}” será encerrada e a reserva de saldo das suas
              solicitações será liberada. O solicitante recebe a justificativa.
            </p>
          </>
        }
        confirmLabel="Recusar demanda"
        keepLabel="Manter demanda"
        justificativaLabel="Justificativa da recusa"
        onClose={() => setRecusando(false)}
        onConfirm={async (texto) => {
          onIniciar();
          let atualizada: Demanda;
          try {
            atualizada = await recusarDemanda(demanda.id, texto);
          } catch (e) {
            throw new Error(mensagemDe(e));
          }
          setRecusando(false);
          aplicarDecisao(atualizada, {
            tipo: "info",
            texto: "Demanda recusada. O solicitante foi notificado.",
          });
        }}
        data-testid="recusar-drawer"
      />
    </div>
  );
}
