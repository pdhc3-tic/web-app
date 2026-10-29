"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Plus, Send } from "lucide-react";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Button } from "@/app/components/ui/Button/Button";
import { ConfirmDeleteDialog } from "@/app/components/ui/ConfirmDeleteDialog/ConfirmDeleteDialog";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { formatDate } from "@/app/lib/datetime";
import { badgeStatusDaDemanda, type Demanda, type SolicitacaoDemanda } from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import { recursoExtraDoBloqueio, type BloqueioRecursoExtra } from "@/app/lib/remanejamentos";
import {
  bloqueiosDaSubmissao,
  pendenciaDeCotacoes,
  removerSolicitacao,
  submeterDemanda,
  type BloqueioSolicitacao,
} from "@/app/lib/solicitacoes";
import { AvisoRecursoExtra } from "../AvisoRecursoExtra";
import { SolicitarRecursoExtra } from "../SolicitarRecursoExtra";
import { DocumentosDemanda, useDocumentosDemanda } from "./DocumentosDemanda";
import { SolicitacaoCartao } from "./SolicitacaoCartao";
import { SolicitacaoForm } from "./SolicitacaoForm";

/** Null: fechado; "nova": nova solicitação; senão, a solicitação em edição. */
type FormAberto = null | "nova" | SolicitacaoDemanda;

/**
 * Montar e submeter a demanda (#295): o solicitante adiciona as solicitações
 * de recurso, anexa os documentos e submete.
 *
 * A submissão é tudo ou nada (`submeter_demanda`): uma solicitação barrada por
 * saldo barra a demanda inteira, e as outras continuam salvas no rascunho,
 * editáveis. Cada barrada mostra o motivo e o que fazer.
 */
export function MontarDemanda({ demanda }: { demanda: Demanda }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const documentos = useDocumentosDemanda(demanda.id);

  const [form, setForm] = useState<FormAberto>(null);
  const [removendo, setRemovendo] = useState<SolicitacaoDemanda | null>(null);
  const [bloqueios, setBloqueios] = useState<Record<number, BloqueioSolicitacao>>({});
  const [recursoExtra, setRecursoExtra] = useState<BloqueioRecursoExtra | null>(null);
  const [erroSubmissao, setErroSubmissao] = useState<string | null>(null);
  const [submetendo, setSubmetendo] = useState(false);

  const semSolicitacoes = demanda.solicitacoes.length === 0;
  // Com equipamento, sem a lista de documentos não há como conferir as
  // cotações: o botão e o handler ficam barrados até ela carregar.
  const pendenciaCotacoes = pendenciaDeCotacoes(demanda, documentos.data, documentos.isError);
  const documentosFalharam = pendenciaCotacoes !== null && documentos.isError && !documentos.data;
  const totalBloqueadas = Object.keys(bloqueios).length;

  /** O bloqueio de uma solicitação que mudou já não vale: a próxima submissão confere de novo. */
  function esquecerBloqueio(id: number) {
    setBloqueios((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }

  async function submeter() {
    setErroSubmissao(null);
    if (pendenciaCotacoes) {
      setErroSubmissao(pendenciaCotacoes);
      return;
    }
    setSubmetendo(true);
    try {
      await submeterDemanda(demanda.id);
      await queryClient.invalidateQueries({ queryKey: qk.demandas.all });
      void queryClient.invalidateQueries({ queryKey: qk.demandasDaAtividade(demanda.activity) });
      showToast(`Demanda "${demanda.titulo}" submetida para aprovação.`, "success");
      router.push(`/sgd/demandas?demanda=${demanda.id}`);
    } catch (err) {
      const barradas = bloqueiosDaSubmissao(err);
      if (barradas) {
        setBloqueios(barradas);
        // O saldo pode ter mudado: o painel de cada solicitação consulta de novo.
        void queryClient.invalidateQueries({ queryKey: ["sgd", "saldo"] });
      } else {
        setBloqueios({});
        setErroSubmissao(err instanceof ApiError ? err.message : "Não foi possível submeter a demanda.");
      }
      setSubmetendo(false);
    }
  }

  return (
    <div className="flex flex-col gap-6" data-testid="montar-demanda">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-text">{demanda.titulo}</h1>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <Badge status={badgeStatusDaDemanda(demanda.status)} label={demanda.status_display} />
            {demanda.despesa_posterior && (
              <span className="text-xs text-warning-text">Despesa posterior à execução</span>
            )}
          </div>
        </div>
        <Link href={`/sgd/demandas?demanda=${demanda.id}`} className="text-sm text-primary hover:underline">
          Ver no painel de demandas
        </Link>
      </div>

      <AvisoRecursoExtra demanda={demanda} />

      <section className="rounded-lg border border-border bg-surface p-6">
        <DefinitionList
          items={[
            {
              label: "Atividade",
              value: (
                <Link href={`/sgp/atividades/${demanda.activity}?tab=demandas`} className="text-primary hover:underline">
                  Abrir ficha da atividade
                </Link>
              ),
            },
            { label: "Território", value: demanda.contexto.territorio_nome },
            { label: "Município", value: demanda.contexto.municipio_nome },
            {
              label: "Plano de Trabalho",
              value: `Meta ${demanda.contexto.meta_numero} · Ação ${demanda.contexto.acao_numero}`,
            },
            { label: "Data prevista", value: formatDate(demanda.contexto.data_prevista) },
            { label: "Justificativa", value: demanda.justificativa || undefined },
          ]}
        />
      </section>

      <section className="flex flex-col gap-4" aria-labelledby="solicitacoes-titulo">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 id="solicitacoes-titulo" className="text-base font-semibold text-text">
              Solicitações de recurso
            </h2>
            <p className="mt-0.5 text-sm text-text-muted">
              Total estimado:{" "}
              <strong className="tabular-nums text-text" data-testid="montar-total">
                {formatCurrencyBRL(demanda.valor_estimado_total)}
              </strong>
            </p>
          </div>
          <Button
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() => setForm("nova")}
            data-testid="solicitacao-adicionar"
          >
            Adicionar solicitação
          </Button>
        </div>

        {semSolicitacoes ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted">
            Nenhuma solicitação ainda. Adicione diárias, passagens, veículo, material gráfico, alimentação ou
            equipamentos.
          </p>
        ) : (
          <ul className="flex list-none flex-col gap-2" data-testid="montar-solicitacoes">
            {demanda.solicitacoes.map((s) => (
              <SolicitacaoCartao
                key={s.id}
                solicitacao={s}
                bloqueio={bloqueios[s.id]}
                onEditar={() => setForm(s)}
                onRemover={() => setRemovendo(s)}
                onRecursoExtra={() => setRecursoExtra(recursoExtraDoBloqueio(s, bloqueios[s.id]))}
              />
            ))}
          </ul>
        )}
      </section>

      <DocumentosDemanda demandaId={demanda.id} />

      <section
        className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-6"
        aria-label="Submeter a demanda"
        data-testid="montar-submissao"
      >
        {totalBloqueadas > 0 && (
          <p
            role="alert"
            className="flex items-start gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
            data-testid="submissao-bloqueada"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            A demanda não foi submetida: {totalBloqueadas === 1 ? "uma solicitação foi barrada" : `${totalBloqueadas} solicitações foram barradas`} por
            saldo. As demais continuam salvas no rascunho. Veja o motivo em cada uma.
          </p>
        )}
        {(erroSubmissao ?? pendenciaCotacoes) && (
          <p
            role="alert"
            className="flex items-start gap-2 rounded-md border border-warning-text bg-warning-bg px-3 py-2.5 text-sm text-warning-text"
            data-testid="submissao-erro"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span className="flex-1">{erroSubmissao ?? pendenciaCotacoes}</span>
            {documentosFalharam && (
              <button
                type="button"
                onClick={() => void documentos.refetch()}
                className="shrink-0 font-medium underline hover:no-underline"
                data-testid="submissao-recarregar-documentos"
              >
                Tentar de novo
              </button>
            )}
          </p>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-text-muted">
            Ao submeter, o valor de cada solicitação é reservado no seu limite e na verba do território, e a
            demanda segue para o Articulador Estadual.
          </p>
          <Button
            leftIcon={<Send className="h-4 w-4" />}
            onClick={submeter}
            loading={submetendo}
            disabled={semSolicitacoes || !!pendenciaCotacoes}
            data-testid="demanda-submeter"
          >
            Submeter para aprovação
          </Button>
        </div>
      </section>

      {form !== null && (
        <SolicitacaoForm
          key={form === "nova" ? "nova" : form.id}
          demanda={demanda}
          solicitacao={form === "nova" ? null : form}
          onClose={() => setForm(null)}
          onSalvo={(salva, nova) => {
            setForm(null);
            esquecerBloqueio(salva.id);
            showToast(nova ? "Solicitação adicionada ao rascunho." : "Solicitação atualizada.", "success");
          }}
        />
      )}

      <ConfirmDeleteDialog
        open={removendo !== null}
        onClose={() => setRemovendo(null)}
        title="Remover solicitação"
        itemName={removendo ? `${removendo.tipo_display} — ${formatCurrencyBRL(removendo.valor_estimado)}` : ""}
        onConfirm={async () => {
          if (!removendo) return;
          await removerSolicitacao(demanda.id, removendo.id);
          esquecerBloqueio(removendo.id);
          setRemovendo(null);
          await queryClient.invalidateQueries({ queryKey: qk.demandas.all });
        }}
      />

      {recursoExtra && (
        <SolicitarRecursoExtra
          open
          demanda={demanda}
          bloqueio={recursoExtra}
          onClose={() => setRecursoExtra(null)}
          onEnviado={() => void queryClient.invalidateQueries({ queryKey: qk.remanejamentos.daDemanda(demanda.id) })}
        />
      )}
    </div>
  );
}
