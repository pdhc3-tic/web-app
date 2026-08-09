"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { notFound, useParams, useSearchParams } from "next/navigation";
import { AlertTriangle, ListChecks, Plus } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { AlertCircleIcon } from "@/app/components/icons";
import Spinner from "@/app/components/icons/Spinner";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { useCanManageWorkPlan } from "@/app/lib/auth/roles";
import { deleteAcao, type Acao } from "@/app/lib/acoes";
import { formatDate } from "@/app/lib/datetime";
import { formatCurrencyBRL } from "@/app/lib/format";
import {
  ODS_OPTIONS,
  badgeStatusForMeta,
  getMeta,
  metaStatusLabel,
  odsShortLabel,
  type MetaDetail,
} from "@/app/lib/metas";
import {
  AcaoSlideOver,
  type AcaoSlideOverMode,
} from "./_components/AcaoSlideOver";
import { AcoesTable } from "./_components/AcoesTable";

type SlideOverState = {
  open: boolean;
  mode: AcaoSlideOverMode;
  acao?: Acao;
};

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

function MetaResumo({ meta }: { meta: MetaDetail }) {
  const ods = meta.ods_ids ?? [];

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-xs uppercase tracking-[0.08em] text-text-muted">
            Meta {meta.numero}
          </span>
          <h2 className="text-lg font-semibold leading-snug text-text">
            {meta.titulo}
          </h2>
        </div>
        <Badge
          status={badgeStatusForMeta(meta.status_calculado)}
          label={metaStatusLabel(meta.status_calculado)}
        />
      </div>

      {meta.descricao && (
        <p className="max-w-prose text-sm leading-relaxed text-text-muted">
          {meta.descricao}
        </p>
      )}

      <DefinitionList
        items={[
          {
            label: "Período",
            value: `${formatDate(meta.data_inicio)} – ${formatDate(meta.data_fim)}`,
          },
          {
            label: "Valor total planejado",
            value: (
              <span className="tabular-nums">
                {formatCurrencyBRL(meta.valor_total_planejado)}
              </span>
            ),
          },
          {
            label: "ODS vinculados",
            value:
              ods.length > 0 ? (
                <span className="flex flex-wrap gap-1">
                  {ods.map((id) => (
                    <Chip
                      key={id}
                      title={ODS_OPTIONS.find((o) => o.id === id)?.label}
                    >
                      {odsShortLabel(id)}
                    </Chip>
                  ))}
                </span>
              ) : null,
          },
        ]}
      />
    </div>
  );
}

function MetaDetalheConteudo() {
  const params = useParams<{ id: string }>();
  const metaId = Number(params.id);

  // Deep-link do Painel de Acompanhamento (FE-9): /sgp/metas/{id}?acao={id}
  // abre a Ação já no formulário de edição.
  const acaoParam = useSearchParams().get("acao");
  const [deepLinkAplicado, setDeepLinkAplicado] = useState(false);

  const { loading: authLoading, canManage } = useCanManageWorkPlan();
  const { showToast } = useToast();

  const [meta, setMeta] = useState<MetaDetail | null>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [naoEncontrada, setNaoEncontrada] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [slideOver, setSlideOver] = useState<SlideOverState>({
    open: false,
    mode: "create",
  });

  const [deleteTarget, setDeleteTarget] = useState<Acao | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Id não numérico na URL é 404 direto — dá para saber no render, sem estado.
  const idInvalido = !Number.isFinite(metaId);

  useEffect(() => {
    if (idInvalido) return;

    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDataLoading(true);
    setError(null);

    getMeta(metaId, controller.signal)
      .then(setMeta)
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 404) {
          setNaoEncontrada(true);
          return;
        }
        if (e instanceof ApiError && e.status === 403) {
          setForbidden(true);
          return;
        }
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar a Meta. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false);
      });

    return () => controller.abort();
  }, [metaId, idInvalido, reloadKey]);

  // Aplica o deep-link uma única vez: depois disso o SlideOver é do usuário, e
  // reabri-lo a cada render impediria que ele fosse fechado.
  useEffect(() => {
    if (deepLinkAplicado || !acaoParam || !meta) return;
    const alvo = meta.acoes.find((a) => String(a.id) === acaoParam);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDeepLinkAplicado(true);
    if (alvo && canManage) {
      setSlideOver({ open: true, mode: "edit", acao: alvo });
    }
  }, [acaoParam, meta, canManage, deepLinkAplicado]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  const closeSlideOver = useCallback(
    () => setSlideOver((prev) => ({ ...prev, open: false })),
    [],
  );

  const handleNew = useCallback(
    () => setSlideOver({ open: true, mode: "create", acao: undefined }),
    [],
  );

  const handleEdit = useCallback(
    (acao: Acao) => setSlideOver({ open: true, mode: "edit", acao }),
    [],
  );

  const handleSaved = useCallback(
    (_acao: Acao, mode: AcaoSlideOverMode) => {
      closeSlideOver();
      showToast(
        mode === "edit"
          ? "Ação atualizada com sucesso."
          : "Ação criada com sucesso.",
        "success",
      );
      // Recarrega o detalhe em vez de mesclar em memória: valor_total da Ação e
      // valor_total_planejado da Meta são derivados e só o backend os calcula.
      reload();
    },
    [closeSlideOver, reload, showToast],
  );

  const handleConfirmDelete = useCallback(async () => {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    try {
      await deleteAcao(deleteTarget.id);
      setDeleteTarget(null);
      showToast("Ação excluída com sucesso.", "success");
      reload();
    } catch (e: unknown) {
      // Ação com Atividades vinculadas → 400 com mensagem pronta do backend.
      setDeleteTarget(null);
      showToast(
        e instanceof ApiError
          ? e.message
          : "Não foi possível excluir a Ação. Tente novamente.",
        "error",
      );
    } finally {
      setDeleting(false);
    }
  }, [deleteTarget, deleting, reload, showToast]);

  if (idInvalido || naoEncontrada) notFound();
  if (authLoading) return <CenteredSpinner />;

  const header = (
    <PageHeader>
      <div className="flex w-full items-center justify-between gap-3">
        <h1 className="truncate text-base font-semibold text-text">
          {meta ? `Meta ${meta.numero} – ${meta.titulo}` : "Meta"}
        </h1>
        {canManage && meta && (
          <Button
            size="sm"
            onClick={handleNew}
            leftIcon={<Plus className="h-4 w-4" />}
            data-testid="acao-nova-btn"
          >
            Nova ação
          </Button>
        )}
      </div>
    </PageHeader>
  );

  if (forbidden) {
    return (
      <>
        {header}
        <RestrictedAccess />
      </>
    );
  }

  const acoes = meta?.acoes ?? [];

  return (
    <div data-testid="meta-detalhe-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Plano de Trabalho", href: "/sgp/metas" },
            { label: meta ? `Meta ${meta.numero}` : "Meta" },
          ]}
        />

        {error ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" />
            </span>
            <p className="max-w-sm text-sm text-text-muted">{error}</p>
            <Button variant="secondary" onClick={reload}>
              Tentar novamente
            </Button>
          </div>
        ) : dataLoading || !meta ? (
          <CenteredSpinner />
        ) : (
          <>
            <MetaResumo meta={meta} />

            <div className="flex flex-col gap-3">
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="text-sm font-semibold uppercase tracking-[0.08em] text-text-muted">
                  Ações vinculadas
                </h2>
                <span className="text-xs tabular-nums text-text-muted">
                  {acoes.length}{" "}
                  {acoes.length === 1 ? "ação" : "ações"}
                </span>
              </div>

              {acoes.length === 0 ? (
                <div className="rounded-lg border border-border bg-surface">
                  <EmptyState
                    icon={<ListChecks className="h-7 w-7" />}
                    title="Nenhuma Ação cadastrada"
                    description={
                      canManage
                        ? "Cadastre a primeira Ação desta Meta para acompanhar execução e custo."
                        : "As Ações desta Meta ainda não foram cadastradas pela UGP."
                    }
                    action={
                      canManage ? (
                        <Button
                          variant="primary"
                          onClick={handleNew}
                          leftIcon={<Plus className="h-4 w-4" />}
                        >
                          Nova ação
                        </Button>
                      ) : undefined
                    }
                  />
                </div>
              ) : (
                <AcoesTable
                  acoes={acoes}
                  canManage={canManage}
                  onEdit={handleEdit}
                  onDelete={setDeleteTarget}
                />
              )}
            </div>
          </>
        )}
      </div>

      {meta && (
        <AcaoSlideOver
          open={slideOver.open}
          onClose={closeSlideOver}
          mode={slideOver.mode}
          metaId={meta.id}
          acao={slideOver.acao}
          onSaved={handleSaved}
        />
      )}

      <SlideOver
        open={deleteTarget !== null}
        onClose={() => {
          if (!deleting) setDeleteTarget(null);
        }}
        title="Excluir Ação?"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => setDeleteTarget(null)}
              disabled={deleting}
            >
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={handleConfirmDelete}
              loading={deleting}
              data-testid="acao-excluir-confirmar"
            >
              Excluir
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-4 px-4 py-6">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertCircleIcon className="h-5 w-5" />
            </span>
            <p className="text-sm leading-relaxed text-text">
              {deleteTarget
                ? `A Ação ${deleteTarget.numero} – ${deleteTarget.descricao} será excluída permanentemente. Ações com Atividades de Campo vinculadas não podem ser excluídas.`
                : ""}
            </p>
          </div>
        </div>
      </SlideOver>
    </div>
  );
}

/**
 * `useSearchParams` exige um limite de Suspense acima dele — mesmo padrão já
 * usado nas telas de login e redefinição de senha.
 */
export default function MetaDetalhePage() {
  return (
    <Suspense fallback={<CenteredSpinner />}>
      <MetaDetalheConteudo />
    </Suspense>
  );
}
