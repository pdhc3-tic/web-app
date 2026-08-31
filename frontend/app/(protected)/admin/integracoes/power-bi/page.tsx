"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Copy, KeyRound, RefreshCw } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Button } from "@/app/components/ui/Button/Button";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import Spinner from "@/app/components/icons/Spinner";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { useIsSuperAdmin } from "@/app/lib/auth/roles";
import { absoluteDateTime, relativeTime } from "@/app/lib/datetime";
import {
  fetchPowerBiConfig,
  PowerBiPendenteError,
  regenerarPowerBiToken,
  type PowerBiConfig,
} from "@/app/lib/integracoesPowerBi";
import { ConfirmarRegeneracaoDialog } from "./_components/ConfirmarRegeneracaoDialog";
import { NovoTokenDialog } from "./_components/NovoTokenDialog";

/**
 * Limite considerado "atrasado" para o snapshot do Power BI (#143 AC-2).
 * O critério da issue diz "intervalo esperado de 1h"; damos folga de 15 min
 * para acomodar variação do worker Celery.
 */
const SNAPSHOT_ATRASO_MS = 75 * 60 * 1000;

function HeaderSlot() {
  return (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">
        Integração Power BI
      </h1>
    </PageHeader>
  );
}

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

export default function PowerBiConfigPage() {
  const { loading: authLoading, isSuperAdmin } = useIsSuperAdmin();
  const { showToast } = useToast();

  const [config, setConfig] = useState<PowerBiConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pendente, setPendente] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [regenerando, setRegenerando] = useState(false);
  const [novoToken, setNovoToken] = useState<string | null>(null);

  // ── Fetch inicial ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isSuperAdmin) return;

    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setLoadError(null);
    setPendente(false);

    fetchPowerBiConfig(controller.signal)
      .then((c) => {
        if (controller.signal.aborted) return;
        setConfig(c);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof PowerBiPendenteError) {
          setPendente(true);
          return;
        }
        setLoadError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar as configurações do Power BI.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [isSuperAdmin, reloadKey]);

  const handleRegenerar = useCallback(async () => {
    setConfirmOpen(false);
    setRegenerando(true);
    try {
      const { novo_token } = await regenerarPowerBiToken();
      setNovoToken(novo_token);
      showToast("Novo token gerado. Copie agora — não será exibido novamente.");
      // Refetch em background para atualizar o mascarado do card principal.
      setReloadKey((k) => k + 1);
    } catch (e) {
      const mensagem =
        e instanceof PowerBiPendenteError
          ? e.message
          : e instanceof ApiError
            ? e.message
            : "Não foi possível regenerar o token. Tente novamente.";
      showToast(mensagem, "error");
    } finally {
      setRegenerando(false);
    }
  }, [showToast]);

  // ── Gating ────────────────────────────────────────────────────────────────

  if (authLoading) {
    return (
      <>
        <HeaderSlot />
        <CenteredSpinner />
      </>
    );
  }

  if (!isSuperAdmin) {
    return (
      <>
        <HeaderSlot />
        <RestrictedAccess />
      </>
    );
  }

  return (
    <>
      <HeaderSlot />

      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "Integrações" },
            { label: "Power BI" },
          ]}
        />

        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-text">
            Integração com Power BI
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Endpoint de exportação consumido pelo Power BI, token de serviço e
            status do último snapshot atualizado.
          </p>
        </div>

        {loading ? (
          <CenteredSpinner />
        ) : pendente ? (
          <BackendPendenteAviso onRetry={() => setReloadKey((k) => k + 1)} />
        ) : loadError ? (
          <CarregamentoFalhouAviso
            mensagem={loadError}
            onRetry={() => setReloadKey((k) => k + 1)}
          />
        ) : config ? (
          <>
            <EndpointCard url={config.url_endpoint} />
            <SnapshotStatusCard atualizadoEm={config.atualizado_em} />
            <TokenCard
              mascarado={config.token_mascarado}
              onRegenerar={() => setConfirmOpen(true)}
              regenerando={regenerando}
            />
          </>
        ) : null}
      </div>

      <ConfirmarRegeneracaoDialog
        open={confirmOpen}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={handleRegenerar}
      />

      <NovoTokenDialog
        token={novoToken}
        onClose={() => setNovoToken(null)}
      />
    </>
  );
}

// ─── Cards ────────────────────────────────────────────────────────────────────

function EndpointCard({ url }: { url: string }) {
  const { showToast } = useToast();

  async function copiar() {
    try {
      await navigator.clipboard.writeText(url);
      showToast("URL copiada.");
    } catch {
      showToast("Não foi possível copiar. Copie manualmente.", "error");
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-6">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium text-text">
          Endpoint da API (Power BI)
        </h3>
        <Button
          size="sm"
          variant="secondary"
          leftIcon={<Copy className="h-4 w-4" />}
          onClick={copiar}
          data-testid="powerbi-copiar-url"
        >
          Copiar
        </Button>
      </div>
      <code
        data-testid="powerbi-url"
        className="block break-all rounded-md bg-surface-muted px-3 py-2 font-mono text-xs text-text"
      >
        {url}
      </code>
      <p className="text-xs text-text-muted">
        Cole esta URL no conector &ldquo;Web&rdquo; do Power BI, autenticando
        com o token de serviço.
      </p>
    </section>
  );
}

function SnapshotStatusCard({
  atualizadoEm,
}: {
  atualizadoEm: string | null;
}) {
  const status = derivarStatusSnapshot(atualizadoEm);

  return (
    <section className="flex items-start gap-3 rounded-lg border border-border bg-surface p-6">
      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-muted">
        <RefreshCw className="h-4 w-4" />
      </span>
      <div className="flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-medium text-text">Último snapshot</h3>
          <span data-testid="powerbi-snapshot-status">
            <Badge status={status.badge} label={status.label} />
          </span>
        </div>
        <p className="mt-1 text-sm text-text-muted">
          {atualizadoEm ? (
            <>
              Atualizado{" "}
              <span
                data-testid="powerbi-snapshot-atualizado-em"
                title={absoluteDateTime(atualizadoEm) ?? undefined}
              >
                {relativeTime(atualizadoEm)}
              </span>
              .
            </>
          ) : (
            "Nunca atualizado — o snapshot ainda não foi gerado."
          )}
        </p>
      </div>
    </section>
  );
}

function TokenCard({
  mascarado,
  onRegenerar,
  regenerando,
}: {
  mascarado: string;
  onRegenerar: () => void;
  regenerando: boolean;
}) {
  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-muted">
          <KeyRound className="h-4 w-4" />
        </span>
        <h3 className="text-sm font-medium text-text">Token de serviço</h3>
      </div>
      <p
        data-testid="powerbi-token-mascarado"
        className="rounded-md bg-surface-muted px-3 py-2 font-mono text-sm text-text"
      >
        {mascarado}
      </p>
      <p className="text-xs text-text-muted">
        O valor completo do token nunca é retornado pelo backend depois de
        gerado. Ao regenerar, o token anterior deixa de funcionar
        imediatamente e o novo é exibido uma única vez.
      </p>
      <div className="flex justify-end">
        <Button
          size="sm"
          leftIcon={
            regenerando ? (
              <Spinner className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )
          }
          disabled={regenerando}
          onClick={onRegenerar}
          data-testid="powerbi-regenerar"
        >
          {regenerando ? "Regenerando…" : "Regenerar token"}
        </Button>
      </div>
    </section>
  );
}

// ─── Estados de vazio/erro ────────────────────────────────────────────────────

function BackendPendenteAviso({ onRetry }: { onRetry: () => void }) {
  return (
    <section
      data-testid="powerbi-backend-pendente"
      className="flex flex-col items-center gap-4 rounded-lg border border-warning-text bg-warning-bg px-6 py-12 text-center"
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-warning-bg text-warning-text">
        <AlertTriangle className="h-6 w-6" />
      </span>
      <div className="max-w-md space-y-1">
        <p className="text-sm font-medium text-warning-text">
          Endpoint administrativo indisponível.
        </p>
        <p className="text-sm text-text-muted">
          O backend ainda não expôs o endpoint de administração do token do
          Power BI. A tela está pronta e passa a funcionar assim que o
          endpoint subir — detalhes técnicos em{" "}
          <code className="font-mono text-xs">
            frontend/docs/pendencias-backend-sprint-8.md
          </code>{" "}
          (item 3).
        </p>
      </div>
      <Button variant="secondary" onClick={onRetry}>
        Tentar novamente
      </Button>
    </section>
  );
}

function CarregamentoFalhouAviso({
  mensagem,
  onRetry,
}: {
  mensagem: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
        <AlertTriangle className="h-6 w-6" />
      </span>
      <p className="max-w-sm text-sm text-text-muted">{mensagem}</p>
      <Button variant="secondary" onClick={onRetry}>
        Tentar novamente
      </Button>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function derivarStatusSnapshot(atualizadoEm: string | null): {
  badge: "concluido" | "em-andamento" | "nao-realizada" | "inativo";
  label: string;
} {
  if (!atualizadoEm) {
    return { badge: "inativo", label: "Sem snapshot" };
  }
  const dt = new Date(atualizadoEm);
  if (Number.isNaN(dt.getTime())) {
    return { badge: "inativo", label: "Sem snapshot" };
  }
  const atrasado = Date.now() - dt.getTime() > SNAPSHOT_ATRASO_MS;
  return atrasado
    ? { badge: "nao-realizada", label: "Atrasado" }
    : { badge: "concluido", label: "Atualizado" };
}
