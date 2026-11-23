"use client";

import { useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { AlertTriangle, Landmark } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { canLancarDotacaoNacional } from "@/app/lib/auth/roles";
import { formatCurrencyBRL, moneyOrNull } from "@/app/lib/format";
import { atualizarPool, fetchPainelOrcamento, lancarDotacaoNacional, valorNumerico } from "@/app/lib/orcamento";
import { qk } from "@/app/lib/queryKeys";
import { listRubricas } from "@/app/lib/tiposSolicitacao";
import { ConfirmarDotacaoDialog, type ConfirmacaoDotacao } from "./_components/ConfirmarDotacaoDialog";
import { DotacaoLinha } from "./_components/DotacaoLinha";
import { montarLinhas } from "./_components/tipos";

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

/**
 * Dotação nacional por rubrica (#438, SGP-RF28).
 *
 * O pool nacional é o topo da hierarquia do orçamento: sem ele a Distribuição
 * não tem teto, o Remanejamento não tem pools e as travas do SGD devolvem saldo
 * zero. Esta tela lança e ajusta o valor aprovado de cada rubrica, com o
 * `POST`/`PATCH` de pools que a Distribuição já usa para os níveis de baixo.
 *
 * ─── O que ainda não existe ──────────────────────────────────────────────────
 *
 * O valor aprovado deveria vir do TED vigente e ser limitado por ele (#437).
 * Enquanto a entidade não existe, o pool nacional não tem teto no servidor; o
 * único limite é o piso (o que já desceu aos estados mais o comprometido e o
 * executado). Ver `frontend/docs/pendencias-backend-sprint-12g.md`.
 */
export default function DotacaoNacionalPage() {
  const { data: session, status } = useSession();
  const pode = status === "authenticated" && canLancarDotacaoNacional(session?.user);
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const rubricasQ = useQuery({
    queryKey: qk.configSgd.rubricas,
    queryFn: ({ signal }) => listRubricas(signal),
    staleTime: 5 * 60_000,
    enabled: pode,
  });
  const poolsQ = useQuery({
    queryKey: qk.dotacaoNacional,
    queryFn: ({ signal }) => fetchPainelOrcamento({ nivel: "nacional" }, signal),
    enabled: pode,
  });

  /** Valor digitado por rubrica, mascarado. Chave: id da rubrica. */
  const [valores, setValores] = useState<Record<number, string>>({});
  /** Erro de 400 por rubrica, ancorado no input. */
  const [erros, setErros] = useState<Record<number, string>>({});
  const [confirmacao, setConfirmacao] = useState<ConfirmacaoDotacao | null>(null);
  const [salvandoId, setSalvandoId] = useState<number | null>(null);

  const linhas = useMemo(
    () => (rubricasQ.data && poolsQ.data ? montarLinhas(rubricasQ.data, poolsQ.data) : null),
    [rubricasQ.data, poolsQ.data],
  );

  const totais = useMemo(() => {
    let dotacao = 0;
    let distribuido = 0;
    for (const l of linhas ?? []) {
      if (!l.pool) continue;
      dotacao += valorNumerico(l.pool.valor_aprovado);
      distribuido += valorNumerico(l.pool.valor_distribuido);
    }
    return { dotacao, distribuido, aDistribuir: dotacao - distribuido };
  }, [linhas]);

  const semDotacao = linhas !== null && linhas.every((l) => l.pool === null);

  const abrirConfirmacao = useCallback(
    (rubricaId: number) => {
      const linha = linhas?.find((l) => l.rubrica.id === rubricaId);
      const valor = moneyOrNull(valores[rubricaId] ?? "");
      if (!linha || valor === null) return;
      setConfirmacao({ linha, valor });
    },
    [linhas, valores],
  );

  const confirmar = useCallback(async () => {
    if (!confirmacao) return;
    const { linha, valor } = confirmacao;
    const rubricaId = linha.rubrica.id;

    setSalvandoId(rubricaId);
    setErros((e) => ({ ...e, [rubricaId]: "" }));
    try {
      if (linha.pool) {
        await atualizarPool(linha.pool.id, valor);
      } else {
        await lancarDotacaoNacional(rubricaId, valor);
      }
      setConfirmacao(null);
      setValores((v) => {
        const proximo = { ...v };
        delete proximo[rubricaId];
        return proximo;
      });
      showToast(
        `${linha.rubrica.nome}: dotação ${linha.pool ? "ajustada para" : "de"} ${formatCurrencyBRL(valor)}${
          linha.pool ? "" : " lançada"
        }.`,
        "success",
      );
      // A dotação é o teto de tudo abaixo: recarrega esta tela, o painel, a
      // distribuição e os saldos que o SGD mostra na montagem e na execução.
      void queryClient.invalidateQueries({ queryKey: ["sgp", "orcamento"] });
      void queryClient.invalidateQueries({ queryKey: ["sgd", "saldo"] });
      void queryClient.invalidateQueries({ queryKey: ["sgd", "execucao", "painel"] });
    } catch (e: unknown) {
      // Todo erro de valor vem em `valor_alocado`; `nivel` é o do pool que já
      // existe (outra pessoa lançou antes). Os dois pertencem a esta rubrica.
      const msg =
        e instanceof ApiError
          ? e.fieldErrors?.length
            ? e.fieldErrors.map((fe) => fe.message).join(" ")
            : e.message
          : "Não foi possível gravar. Tente novamente.";
      setErros((err) => ({ ...err, [rubricaId]: msg }));
      setConfirmacao(null);
      // Se o pool foi criado por outra pessoa, a linha precisa passar a "Ajustar".
      if (e instanceof ApiError && e.fieldErrors?.some((fe) => fe.field === "nivel")) {
        void queryClient.invalidateQueries({ queryKey: qk.dotacaoNacional });
      }
    } finally {
      setSalvandoId(null);
    }
  }, [confirmacao, queryClient, showToast]);

  const header = (
    <PageHeader>
      <div className="flex w-full items-center justify-between gap-3">
        <h1 className="truncate text-base font-semibold text-text">Dotação nacional</h1>
        {pode && (
          <Button
            as="a"
            size="sm"
            variant="secondary"
            href="/sgp/orcamento/distribuicao"
            data-testid="dotacao-ir-distribuicao"
          >
            Distribuir aos estados
          </Button>
        )}
      </div>
    </PageHeader>
  );

  if (status === "loading") return <CenteredSpinner />;

  if (!pode) {
    return (
      <>
        {header}
        <RestrictedAccess
          title="Dotação restrita"
          description="Apenas a UGP e o Super Admin lançam a dotação nacional. Você pode acompanhar os valores no Painel de Orçamento."
        />
      </>
    );
  }

  const erroCarga = rubricasQ.error ?? poolsQ.error;

  return (
    <div data-testid="dotacao-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Painel de Orçamento", href: "/sgp/orcamento" },
            { label: "Dotação nacional" },
          ]}
        />

        <p className="max-w-prose text-sm text-text-muted">
          Lance o valor aprovado de cada rubrica no nível nacional. Ele é o teto do que a Distribuição
          repassa aos estados e, deles, aos territórios. Cada gravação fica registrada em seu nome.
        </p>

        {erroCarga ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" aria-hidden />
            </span>
            <p className="max-w-sm text-sm text-text-muted">
              {erroCarga instanceof ApiError ? erroCarga.message : "Não foi possível carregar a dotação nacional."}
            </p>
            <Button
              variant="secondary"
              onClick={() => {
                void rubricasQ.refetch();
                void poolsQ.refetch();
              }}
            >
              Tentar novamente
            </Button>
          </div>
        ) : linhas === null ? (
          <CenteredSpinner />
        ) : linhas.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<Landmark className="h-7 w-7" />}
              title="Nenhuma rubrica ativa"
              description="O catálogo de rubricas está vazio. Sem rubrica não há dotação a lançar."
            />
          </div>
        ) : (
          <>
            <dl
              className="grid grid-cols-1 gap-3 rounded-lg border border-border bg-surface p-4 sm:grid-cols-3"
              data-testid="dotacao-totais"
            >
              <div>
                <dt className="text-xs text-text-muted">Dotação nacional</dt>
                <dd className="mt-1 text-lg font-semibold text-text tabular-nums" data-testid="dotacao-total">
                  {formatCurrencyBRL(totais.dotacao)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-text-muted">Distribuído aos estados</dt>
                <dd className="mt-1 text-lg font-semibold text-text tabular-nums">
                  {formatCurrencyBRL(totais.distribuido)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-text-muted">A distribuir</dt>
                <dd className="mt-1 text-lg font-semibold text-text tabular-nums">
                  {formatCurrencyBRL(totais.aDistribuir)}
                </dd>
              </div>
            </dl>

            {semDotacao && (
              <p
                className="rounded-md border border-border bg-surface-muted px-3 py-2.5 text-sm text-text-muted"
                data-testid="dotacao-sem-lancamento"
              >
                Nenhuma rubrica tem dotação nacional ainda. Enquanto não houver, a Distribuição não tem
                teto e o SGD não libera saldo para as demandas.
              </p>
            )}

            <ul
              aria-busy={poolsQ.isFetching}
              className="rounded-lg border border-border bg-surface"
              data-testid="dotacao-rubricas"
            >
              {linhas.map((linha) => {
                const id = linha.rubrica.id;
                return (
                  <DotacaoLinha
                    key={id}
                    linha={linha}
                    valor={valores[id] ?? ""}
                    onChange={(v) => {
                      setValores((atual) => ({ ...atual, [id]: v }));
                      setErros((atual) => ({ ...atual, [id]: "" }));
                    }}
                    onGravar={() => abrirConfirmacao(id)}
                    erro={erros[id] || undefined}
                    salvando={salvandoId === id}
                    desabilitado={salvandoId !== null && salvandoId !== id}
                  />
                );
              })}
            </ul>
          </>
        )}
      </div>

      <ConfirmarDotacaoDialog
        confirmacao={confirmacao}
        onCancel={() => setConfirmacao(null)}
        onConfirm={confirmar}
        salvando={salvandoId !== null}
      />
    </div>
  );
}
