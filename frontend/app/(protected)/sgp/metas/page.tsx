"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Plus, Target } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { AlertCircleIcon } from "@/app/components/icons";
import Spinner from "@/app/components/icons/Spinner";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { useCanManageWorkPlan } from "@/app/lib/auth/roles";
import { deleteMeta, listMetas, type MetaListItem } from "@/app/lib/metas";
import {
  MetaSlideOver,
  type MetaSlideOverMode,
} from "./_components/MetaSlideOver";
import { MetasTable } from "./_components/MetasTable";

type SlideOverState = {
  open: boolean;
  mode: MetaSlideOverMode;
  meta?: MetaListItem;
};

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

export default function MetasPage() {
  const { loading: authLoading, canManage } = useCanManageWorkPlan();
  const { showToast } = useToast();

  const [metas, setMetas] = useState<MetaListItem[]>([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [slideOver, setSlideOver] = useState<SlideOverState>({
    open: false,
    mode: "create",
  });

  const [deleteTarget, setDeleteTarget] = useState<MetaListItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDataLoading(true);
    setError(null);

    listMetas(controller.signal)
      .then(setMetas)
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 403) {
          setForbidden(true);
          return;
        }
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar as Metas. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false);
      });

    return () => controller.abort();
  }, [reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  const closeSlideOver = useCallback(
    () => setSlideOver((prev) => ({ ...prev, open: false })),
    [],
  );

  const handleNew = useCallback(
    () => setSlideOver({ open: true, mode: "create", meta: undefined }),
    [],
  );

  const handleEdit = useCallback(
    (meta: MetaListItem) => setSlideOver({ open: true, mode: "edit", meta }),
    [],
  );

  const handleSaved = useCallback(
    (_meta: unknown, mode: MetaSlideOverMode) => {
      closeSlideOver();
      showToast(
        mode === "edit"
          ? "Meta atualizada com sucesso."
          : "Meta criada com sucesso.",
        "success",
      );
      // Recarrega em vez de mesclar em memória: valor_total_planejado e
      // status_calculado são derivados das Ações e só o backend os calcula.
      reload();
    },
    [closeSlideOver, reload, showToast],
  );

  const handleConfirmDelete = useCallback(async () => {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    try {
      await deleteMeta(deleteTarget.id);
      setDeleteTarget(null);
      showToast("Meta excluída com sucesso.", "success");
      reload();
    } catch (e: unknown) {
      // Meta com Ações vinculadas → 400 com mensagem pronta do backend.
      // A listagem continua intacta; só o toast comunica o bloqueio.
      setDeleteTarget(null);
      showToast(
        e instanceof ApiError
          ? e.message
          : "Não foi possível excluir a Meta. Tente novamente.",
        "error",
      );
    } finally {
      setDeleting(false);
    }
  }, [deleteTarget, deleting, reload, showToast]);

  if (authLoading) {
    return <CenteredSpinner />;
  }

  const header = (
    <PageHeader>
      <div className="flex w-full items-center justify-between gap-3">
        <h1 className="truncate text-base font-semibold text-text">
          Metas do Plano de Trabalho
        </h1>
        {canManage && !forbidden && (
          <Button
            size="sm"
            onClick={handleNew}
            leftIcon={<Plus className="h-4 w-4" />}
            data-testid="meta-nova-btn"
          >
            Nova meta
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

  const showEmpty = !dataLoading && !error && metas.length === 0;

  return (
    <div data-testid="metas-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Plano de Trabalho" },
          ]}
        />

        <p className="text-sm text-text-muted">
          As 7 Metas do PDHC III. O valor total planejado é a soma das Ações
          vinculadas a cada Meta.
        </p>

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
        ) : showEmpty ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={<Target className="h-7 w-7" />}
              title="Nenhuma Meta cadastrada"
              description={
                canManage
                  ? "Comece cadastrando a primeira Meta do Plano de Trabalho."
                  : "As Metas do Plano de Trabalho ainda não foram cadastradas pela UGP."
              }
              action={
                canManage ? (
                  <Button
                    variant="primary"
                    onClick={handleNew}
                    leftIcon={<Plus className="h-4 w-4" />}
                  >
                    Nova meta
                  </Button>
                ) : undefined
              }
            />
          </div>
        ) : (
          <MetasTable
            metas={metas}
            loading={dataLoading}
            canManage={canManage}
            onEdit={handleEdit}
            onDelete={setDeleteTarget}
          />
        )}
      </div>

      <MetaSlideOver
        open={slideOver.open}
        onClose={closeSlideOver}
        mode={slideOver.mode}
        metaListItem={slideOver.meta}
        onSaved={handleSaved}
      />

      <SlideOver
        open={deleteTarget !== null}
        onClose={() => {
          if (!deleting) setDeleteTarget(null);
        }}
        title="Excluir Meta?"
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
              disabled={deleting}
              data-testid="meta-excluir-confirmar"
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
                ? `A Meta ${deleteTarget.numero} – ${deleteTarget.titulo} será excluída permanentemente. Metas com Ações vinculadas não podem ser excluídas.`
                : ""}
            </p>
          </div>
        </div>
      </SlideOver>
    </div>
  );
}
