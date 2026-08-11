"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, KeyRound, RefreshCw } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import Spinner from "@/app/components/icons/Spinner";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { useIsSuperAdmin } from "@/app/lib/auth/roles";
import { absoluteDateTime, relativeTime } from "@/app/lib/datetime";
import {
  CONFIG_FIELD_LABEL,
  EMPTY_CONFIG,
  configEquals,
  fetchGoogleCalendarConfig,
  fetchGoogleCalendarStatus,
  saveGoogleCalendarConfig,
  type GoogleCalendarConfig,
  type GoogleCalendarStatus,
} from "@/app/lib/integracoes";
import { RemindersEditor } from "./_components/RemindersEditor";
import { Toggle } from "./_components/Toggle";

const CALENDAR_ID_FIELD = "gcal-calendario-destino-id";
const REMINDERS_FIELD = "gcal-lembretes";
const ENABLED_FIELD = "gcal-integracao-ativa";

function HeaderSlot() {
  return (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">
        Google Calendar
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

export default function GoogleCalendarConfigPage() {
  const { loading: authLoading, isSuperAdmin } = useIsSuperAdmin();
  const { showToast } = useToast();

  const [original, setOriginal] = useState<GoogleCalendarConfig>(EMPTY_CONFIG);
  const [form, setForm] = useState<GoogleCalendarConfig>(EMPTY_CONFIG);
  const [status, setStatus] = useState<GoogleCalendarStatus | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!isSuperAdmin) return;

    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setLoadError(null);

    Promise.all([
      fetchGoogleCalendarConfig(controller.signal),
      // Nunca rejeita: sem o endpoint agregado devolve `indisponivel`.
      fetchGoogleCalendarStatus(controller.signal),
    ])
      .then(([config, statusResult]) => {
        if (controller.signal.aborted) return;
        setOriginal(config);
        setForm(config);
        setStatus(statusResult);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setLoadError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar as configurações da integração.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [isSuperAdmin, reloadKey]);

  const patch = useCallback((p: Partial<GoogleCalendarConfig>) => {
    setForm((prev) => ({ ...prev, ...p }));
    setFieldErrors((prev) => {
      if (Object.keys(p).every((k) => !(k in prev))) return prev;
      const next = { ...prev };
      for (const k of Object.keys(p)) delete next[k];
      return next;
    });
  }, []);

  const dirty = !configEquals(original, form);

  async function handleSave() {
    if (saving || !dirty) return;
    setSaving(true);
    setFieldErrors({});

    try {
      // A view é @transaction.atomic — ou grava tudo, ou nada. Não há estado
      // parcial a reconciliar; adotamos o payload devolvido como novo original.
      const persistido = await saveGoogleCalendarConfig(form);
      setOriginal(persistido);
      setForm(persistido);
      showToast("Configurações salvas.", "success");
    } catch (e: unknown) {
      if (e instanceof ApiError && e.fieldErrors?.length) {
        const mapped: Record<string, string> = {};
        for (const fe of e.fieldErrors) mapped[fe.field] = fe.message;
        setFieldErrors(mapped);
        const nomes = e.fieldErrors
          .map(
            (fe) =>
              CONFIG_FIELD_LABEL[
                fe.field as keyof GoogleCalendarConfig
              ] ?? fe.field,
          )
          .join(", ");
        showToast(`Corrija os campos destacados: ${nomes}.`, "error");
        return;
      }
      showToast(
        e instanceof ApiError
          ? e.message
          : "Não foi possível salvar as configurações. Tente novamente.",
        "error",
      );
    } finally {
      setSaving(false);
    }
  }

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
            { label: "Google Calendar" },
          ]}
        />

        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-text">
            Integração com Google Calendar
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Configurações do calendário destino e dos lembretes das atividades
            sincronizadas.
          </p>
        </div>

        {loading ? (
          <CenteredSpinner />
        ) : loadError ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" />
            </span>
            <p className="max-w-sm text-sm text-text-muted">{loadError}</p>
            <Button
              variant="secondary"
              onClick={() => setReloadKey((k) => k + 1)}
            >
              Tentar novamente
            </Button>
          </div>
        ) : (
          <>
            <StatusSection status={status} />

            <CredenciaisSection />

            <section className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-6">
              <h3 className="text-sm font-medium text-text">Configuração</h3>

              <Input
                id={CALENDAR_ID_FIELD}
                label="Calendário destino (ID)"
                value={form.calendario_destino_id}
                onChange={(e) =>
                  patch({ calendario_destino_id: e.target.value })
                }
                placeholder="agenda@organizacao.org.br"
                helperText="ID do calendário no Google, geralmente um e-mail ou terminado em @group.calendar.google.com."
                error={fieldErrors.calendario_destino_id}
                disabled={saving}
              />

              <RemindersEditor
                id={REMINDERS_FIELD}
                value={form.lembretes}
                onChange={(lembretes) => patch({ lembretes })}
                error={fieldErrors.lembretes}
                disabled={saving}
              />

              <div className="border-t border-border pt-5">
                <Toggle
                  id={ENABLED_FIELD}
                  checked={form.integracao_ativa}
                  onChange={(integracao_ativa) => patch({ integracao_ativa })}
                  label="Integração ativa"
                  description="Quando desativada, novas sincronizações não são enfileiradas."
                  disabled={saving}
                />
              </div>
            </section>

            <div className="flex items-center justify-end gap-3">
              {dirty && (
                <span className="text-xs text-text-muted">
                  Alterações não salvas
                </span>
              )}
              <Button onClick={handleSave} loading={saving} disabled={!dirty}>
                Salvar alterações
              </Button>
            </div>
          </>
        )}
      </div>
    </>
  );
}

/** Bloco meramente informativo — nenhuma credencial é lida, exibida ou editável. */
function CredenciaisSection() {
  return (
    <section className="flex items-start gap-3 rounded-lg border border-border bg-surface p-6">
      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-muted">
        <KeyRound className="h-4 w-4" />
      </span>
      <div>
        <h3 className="text-sm font-medium text-text">Credenciais OAuth2</h3>
        <p className="mt-1 text-sm leading-relaxed text-text-muted">
          As credenciais da conta de serviço são configuradas por variável de
          ambiente no servidor. Por segurança, não são exibidas nem editáveis
          por esta tela.
        </p>
      </div>
    </section>
  );
}

const ESTADO_BADGE: Record<
  GoogleCalendarStatus["estado"],
  {
    status: "concluido" | "em-andamento" | "nao-realizada" | "inativo";
    label: string;
  }
> = {
  ok: { status: "concluido", label: "Sincronizado" },
  pendente: { status: "em-andamento", label: "Sincronização em andamento" },
  erro: { status: "nao-realizada", label: "Falha na sincronização" },
  nunca_executada: { status: "inativo", label: "Nunca sincronizado" },
  indisponivel: { status: "inativo", label: "Indisponível" },
};

function StatusSection({ status }: { status: GoogleCalendarStatus | null }) {
  const estado = status?.estado ?? "indisponivel";
  const badge = ESTADO_BADGE[estado];

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-6">
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-text">
          <RefreshCw className="h-4 w-4 text-text-muted" aria-hidden="true" />
          Status da sincronização
        </h3>
        <Badge status={badge.status} label={badge.label} />
      </div>

      {estado === "indisponivel" ? (
        <p className="text-sm text-text-muted">
          O backend ainda não expõe o status agregado da integração. A
          sincronização é registrada por atividade, no campo{" "}
          <span className="font-medium text-text">Status de sincronização</span>{" "}
          de cada uma.
        </p>
      ) : (
        <>
          <p className="text-sm text-text-muted">
            Última sincronização:{" "}
            {status?.ultimaSincronizacao ? (
              <span
                className="text-text"
                title={absoluteDateTime(status.ultimaSincronizacao)}
              >
                {relativeTime(status.ultimaSincronizacao)}
              </span>
            ) : (
              <span className="text-text">nunca executada</span>
            )}
          </p>

          {status && status.falhasRecentes > 0 && (
            <p className="text-sm text-error-text">
              {status.falhasRecentes} falha(s) registrada(s) recentemente.
            </p>
          )}

          {status?.ultimoErro && (
            <p className="rounded-md bg-error-bg px-3 py-2 text-xs text-error-text">
              {status.ultimoErro}
            </p>
          )}
        </>
      )}
    </section>
  );
}
