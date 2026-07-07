"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import {
  Bell,
  Calendar,
  Database,
  FileText,
  Heart,
  Smartphone,
  Wallet,
  Users,
} from "lucide-react";
import { apiClient } from "@/app/lib/api";
import { relativeTime } from "@/app/lib/datetime";

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** Espelha apps/core/serializers.py::NotificationSerializer. */
export type Notification = {
  id: number;
  tipo: string;
  titulo: string;
  mensagem: string;
  link: string;
  modulo_origem: string;
  evento: string;
  enviado_em: string | null;
  lido_em: string | null;
  status: string;
  tentativas: number;
};

type UnreadCountResponse = { count: number };
type NotificationListResponse = { results: Notification[] };

// ─── Constantes ─────────────────────────────────────────────────────────────

const POLL_INTERVAL_MS = 60_000;
const PULSE_DURATION_MS = 2_000;
const LIST_PAGE_SIZE = 10;

// Ícone do módulo de origem — switch retornando JSX direto (mesma abordagem do
// DashboardCardIcon). Evita derivar um componente em tempo de render, o que
// dispararia a regra react-hooks/static-components.
function ModuleOriginIcon({ modulo }: { modulo: string }) {
  const props = { className: "h-5 w-5", "aria-hidden": true as const };
  switch (modulo.trim().toLowerCase()) {
    case "sca":
      return <Smartphone {...props} />;
    case "sgd":
      return <FileText {...props} />;
    case "sge":
      return <Calendar {...props} />;
    case "sgf":
      return <Wallet {...props} />;
    case "sgp":
      return <Users {...props} />;
    case "sgs":
      return <Heart {...props} />;
    case "core":
      return <Database {...props} />;
    default:
      return <Bell {...props} />;
  }
}

function isUnread(n: Notification): boolean {
  return n.lido_em === null;
}

// ─── Hook: contagem de não-lidas com polling sensível à visibilidade ─────────

function useUnreadCount() {
  const [count, setCount] = useState(0);
  // Guarda o valor anterior para detectar AUMENTO (dispara o pulso).
  const prevRef = useRef(0);
  // A primeira leitura apenas estabelece a linha de base — não pulsa.
  const initializedRef = useRef(false);
  const [pulsing, setPulsing] = useState(false);
  const pulseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const applyCount = useCallback((next: number) => {
    if (initializedRef.current && next > prevRef.current) {
      setPulsing(true);
      if (pulseTimer.current) clearTimeout(pulseTimer.current);
      pulseTimer.current = setTimeout(() => setPulsing(false), PULSE_DURATION_MS);
    }
    initializedRef.current = true;
    prevRef.current = next;
    setCount(next);
  }, []);

  const fetchCount = useCallback(async () => {
    try {
      const res = await apiClient("/api/v1/notifications/me/unread-count/");
      const data: UnreadCountResponse = await res.json();
      applyCount(data.count);
    } catch {
      // Silencioso: o polling tenta de novo no próximo ciclo.
    }
  }, [applyCount]);

  // Atualização local imediata (otimista) sem esperar o próximo poll.
  const setCountLocal = useCallback((next: number) => {
    prevRef.current = next;
    setCount(next);
  }, []);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;

    function start() {
      if (interval) return;
      void fetchCount();
      interval = setInterval(() => void fetchCount(), POLL_INTERVAL_MS);
    }

    function stop() {
      if (interval) {
        clearInterval(interval);
        interval = null;
      }
    }

    function onVisibility() {
      // Só faz polling com a aba visível; pausa em background.
      if (document.visibilityState === "visible") start();
      else stop();
    }

    onVisibility();
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      stop();
      if (pulseTimer.current) clearTimeout(pulseTimer.current);
    };
  }, [fetchCount]);

  return { count, pulsing, refresh: fetchCount, setCountLocal };
}

// ─── Subcomponente: item da lista ───────────────────────────────────────────

function NotificationItem({
  notification,
  onRead,
  onClose,
}: {
  notification: Notification;
  onRead: (n: Notification) => void;
  onClose: () => void;
}) {
  const unread = isUnread(notification);
  const hasLink = notification.link.length > 0;
  const internal = notification.link.startsWith("/");

  const content = (
    <>
      <span className="mt-0.5 shrink-0 text-text-muted">
        <ModuleOriginIcon modulo={notification.modulo_origem} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          {unread && (
            <span
              className="h-2 w-2 shrink-0 rounded-full bg-info-text"
              aria-hidden="true"
            />
          )}
          <span className="truncate text-sm font-medium text-text">
            {notification.titulo}
          </span>
        </span>
        <span className="mt-0.5 line-clamp-2 text-xs text-text-muted">
          {notification.mensagem}
        </span>
        <span className="mt-1 block text-micro text-text-muted">
          {relativeTime(notification.enviado_em)}
        </span>
      </span>
    </>
  );

  const className = [
    "flex w-full items-start gap-3 px-4 py-3 text-left transition-colors",
    "hover:bg-surface-muted focus-visible:outline-none focus-visible:bg-surface-muted",
    unread ? "bg-surface-warm" : "bg-surface",
  ].join(" ");

  // Item com link navega (e fecha o dropdown); sem link, só marca como lido.
  function handleNavigate() {
    onRead(notification);
    onClose();
  }

  // Link interno → navegação SPA; link externo → âncora; sem link → botão.
  if (hasLink && internal) {
    return (
      <li>
        <Link href={notification.link} className={className} onClick={handleNavigate}>
          {content}
        </Link>
      </li>
    );
  }
  if (hasLink) {
    return (
      <li>
        <a href={notification.link} className={className} onClick={handleNavigate}>
          {content}
        </a>
      </li>
    );
  }
  return (
    <li>
      <button type="button" className={className} onClick={() => onRead(notification)}>
        {content}
      </button>
    </li>
  );
}

// ─── NotificationBell ───────────────────────────────────────────────────────

export function NotificationBell() {
  const { count, pulsing, refresh, setCountLocal } = useUnreadCount();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);

  const panelId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const close = useCallback(() => setOpen(false), []);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient(
        `/api/v1/notifications/me/?limit=${LIST_PAGE_SIZE}`,
      );
      const data: NotificationListResponse = await res.json();
      setItems(data.results);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Carrega a lista ao abrir. loadList faz setState (loading) de forma síncrona;
  // é uma busca legítima disparada pela abertura — mesmo padrão já adotado no
  // repo (PageHeader, ThemeToggle).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (open) void loadList();
  }, [open, loadList]);

  // Esc fecha + clique fora fecha.
  useEffect(() => {
    if (!open) return;

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
        buttonRef.current?.focus();
        return;
      }
      // Foco preso: cicla o Tab dentro do painel.
      if (e.key === "Tab" && panelRef.current) {
        const focusables = panelRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const active = document.activeElement;
        if (e.shiftKey && active === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    function onPointerDown(e: MouseEvent) {
      const target = e.target as Node;
      if (
        !panelRef.current?.contains(target) &&
        !buttonRef.current?.contains(target)
      ) {
        close();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open, close]);

  // Move o foco para dentro do painel ao abrir.
  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  // Marca uma notificação como lida — otimista, com rollback em erro.
  const markRead = useCallback(
    (notification: Notification) => {
      if (isUnread(notification)) {
        const snapshot = items;
        const snapshotCount = count;
        const nowIso = new Date().toISOString();
        setItems((prev) =>
          prev.map((n) => (n.id === notification.id ? { ...n, lido_em: nowIso } : n)),
        );
        setCountLocal(Math.max(0, count - 1));

        void apiClient(`/api/v1/notifications/${notification.id}/read/`, {
          method: "PATCH",
        }).catch(() => {
          // Rollback visual + ressincroniza a contagem com o servidor.
          setItems(snapshot);
          setCountLocal(snapshotCount);
          void refresh();
        });
      }
    },
    [items, count, refresh, setCountLocal],
  );

  // Marca todas como lidas — otimista, com rollback em erro.
  const markAllRead = useCallback(() => {
    const snapshot = items;
    const snapshotCount = count;
    const nowIso = new Date().toISOString();
    setItems((prev) =>
      prev.map((n) => (n.lido_em ? n : { ...n, lido_em: nowIso })),
    );
    setCountLocal(0);

    void apiClient("/api/v1/notifications/mark-all-read/", {
      method: "POST",
    }).catch(() => {
      setItems(snapshot);
      setCountLocal(snapshotCount);
      void refresh();
    });
  }, [items, count, refresh, setCountLocal]);

  const badgeLabel = count > 9 ? "9+" : String(count);

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={`Notificações, ${count} não lidas`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        className="relative inline-flex h-9 w-9 items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-surface-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
      >
        <Bell className="h-5 w-5" aria-hidden="true" />

        {count > 0 && (
          <span className="absolute -right-0.5 -top-0.5 inline-flex">
            {/* Pulso de 2s ao chegar notificação nova; oculto com reduced-motion. */}
            {pulsing && (
              <span className="absolute inset-0 inline-flex h-full w-full animate-ping rounded-full bg-error opacity-75 motion-reduce:hidden" />
            )}
            <span className="relative inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-error px-1 text-micro font-semibold text-white">
              {badgeLabel}
            </span>
          </span>
        )}
      </button>

      {open && (
        <div
          ref={panelRef}
          id={panelId}
          role="dialog"
          aria-label="Notificações"
          tabIndex={-1}
          className="absolute right-0 top-full z-30 mt-2 flex max-h-96 w-80 flex-col overflow-hidden rounded-lg border border-border bg-surface shadow-md outline-none"
        >
          <header className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold text-text">Notificações</h2>
          </header>

          <ul
            aria-live="polite"
            className="flex-1 divide-y divide-border overflow-y-auto"
          >
            {loading && items.length === 0 ? (
              <li className="px-4 py-6 text-center text-sm text-text-muted">
                Carregando…
              </li>
            ) : items.length === 0 ? (
              <li className="flex flex-col items-center gap-2 px-4 py-8 text-center">
                <Bell className="h-8 w-8 text-text-muted" aria-hidden="true" />
                <span className="text-sm text-text-muted">
                  Nenhuma notificação ainda
                </span>
              </li>
            ) : (
              items.map((n) => (
                <NotificationItem
                  key={n.id}
                  notification={n}
                  onRead={markRead}
                  onClose={close}
                />
              ))
            )}
          </ul>

          <footer className="flex shrink-0 items-center justify-between gap-2 border-t border-border px-4 py-2">
            <button
              type="button"
              onClick={markAllRead}
              className="rounded-sm text-xs font-medium text-primary transition-colors hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Marcar todas como lidas
            </button>
            <Link
              href="/notificacoes"
              onClick={close}
              className="rounded-sm text-xs font-medium text-text-muted transition-colors hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Ver todas
            </Link>
          </footer>
        </div>
      )}
    </div>
  );
}

