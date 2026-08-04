"use client";

import {
  ReactNode,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { createPortal } from "react-dom";
import { XIcon } from "../../icons";

// ─── Tipos ────────────────────────────────────────────────────────────────────

export type SlideOverWidth = "default" | "wide";

export type SlideOverProps = {
  /** Controla se o painel está visível. */
  open: boolean;
  /** Chamado quando o painel deve fechar (Esc, clique no backdrop, botão ✕). */
  onClose: () => void;
  /** Título do painel — referenciado por aria-labelledby. */
  title: string;
  /**
   * Badge opcional à esquerda do título.
   * Passe um <Badge status="..." /> do componente Badge.
   */
  badge?: ReactNode;
  /**
   * Botões de ação opcionais no header (ex.: Editar, Duplicar).
   * Posicionados entre a área do título e o botão de fechar.
   */
  actions?: ReactNode;
  /** Breadcrumb opcional exibido logo abaixo do header. */
  breadcrumb?: ReactNode;
  /** Barra de abas opcional exibida abaixo do breadcrumb (ou do header, se não houver breadcrumb). */
  tabs?: ReactNode;
  /**
   * Rodapé fixo opcional (ex.: Salvar / Cancelar).
   * Permanece fixo na base do painel.
   */
  footer?: ReactNode;
  /** Conteúdo scrollável do corpo do painel. */
  children: ReactNode;
  /**
   * Largura do painel em desktop (≥ breakpoint sm).
   * - "default" → max-w-[480px]
   * - "wide"    → max-w-[600px]
   * Em mobile o painel ocupa 100% da largura da viewport.
   */
  width?: SlideOverWidth;
};

// ─── Mapa de larguras ─────────────────────────────────────────────────────────

const widthClass: Record<SlideOverWidth, string> = {
  default: "sm:max-w-[480px]",
  wide: "sm:max-w-[600px]",
};

// ─── Funções estáveis para useSyncExternalStore ───────────────────────────────
// Definidas fora do componente para garantir identidade de referência estável.

function subscribeNoop() {
  return () => {};
}
function getPortalTarget() {
  return document.body;
}
function getPortalTargetServer(): null {
  return null;
}

// ─── SlideOver ────────────────────────────────────────────────────────────────

export function SlideOver({
  open,
  onClose,
  title,
  badge,
  actions,
  breadcrumb,
  tabs,
  footer,
  children,
  width = "default",
}: SlideOverProps) {
  const titleId = useId();

  // Dois estados separados para animar o fechamento antes de desmontar o painel
  // do DOM. `mounted` mantém o elemento no DOM; `visible` aciona a transição CSS
  // (translateX).
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);

  // Alvo do portal — useSyncExternalStore garante SSR-safe sem setState em efeito.
  // No servidor getPortalTargetServer retorna null, impedindo renderização do portal.
  const portalTarget = useSyncExternalStore(
    subscribeNoop,
    getPortalTarget,
    getPortalTargetServer,
  );

  // Armazena o elemento focado antes de abrir o painel para restaurar o foco ao fechar.
  const returnFocusRef = useRef<Element | null>(null);

  // O título do painel recebe foco programático ao abrir.
  const titleRef = useRef<HTMLHeadingElement>(null);

  // ── Montar / desmontar com animação ──────────────────────────────────────
  useEffect(() => {
    if (open) {
      returnFocusRef.current = document.activeElement;
      // setMounted e setVisible são chamados dentro de callbacks de rAF —
      // não diretamente no corpo do efeito — para respeitar a regra do React
      // Compiler e garantir que o elemento esteja no DOM antes de aplicar
      // a classe de transição que dispara o slide-in.
      const raf = requestAnimationFrame(() => {
        setMounted(true);
        requestAnimationFrame(() => setVisible(true));
      });
      return () => cancelAnimationFrame(raf);
    } else {
      // queueMicrotask mantém o setState fora do corpo direto do efeito
      // (requisito do React Compiler) sem atraso visível para a animação.
      queueMicrotask(() => setVisible(false));
    }
  }, [open]);

  // Chamado ao término da transição CSS. Se o painel estiver invisível,
  // remove-o do DOM e devolve o foco ao elemento que disparou a abertura.
  const handleTransitionEnd = useCallback(() => {
    if (!visible) {
      setMounted(false);
      if (returnFocusRef.current instanceof HTMLElement) {
        returnFocusRef.current.focus();
      }
      returnFocusRef.current = null;
    }
  }, [visible]);

  // ── Foco no título quando o painel se torna visível ───────────────────────
  useEffect(() => {
    if (visible) {
      titleRef.current?.focus();
    }
  }, [visible]);

  // ── Tecla Escape ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  // ── Nada a renderizar ────────────────────────────────────────────────────
  if (!portalTarget || !mounted) return null;

  // ── Conteúdo do painel ───────────────────────────────────────────────────
  const panel = (
    // Backdrop — sobrepõe a tela por trás do painel.
    <div
      className={[
        "fixed inset-0 z-40 flex justify-end",
        "transition-opacity motion-reduce:transition-none duration-250 ease-out",
        visible ? "opacity-100" : "opacity-0",
      ].join(" ")}
      aria-hidden="true"
      onClick={onClose}
    >
      {/* Scrim semitransparente */}
      <div className="absolute inset-0 bg-black/30" />

      {/*
        Painel — stopPropagation impede que cliques dentro do painel
        fechem via o handler do backdrop acima.
      */}
      <div
        role="dialog"
        aria-modal="false"
        aria-labelledby={titleId}
        className={[
          // Layout
          "relative flex flex-col w-full bg-surface shadow-xl",
          widthClass[width],
          // Animação de slide — painel entra da direita.
          "transition-transform motion-reduce:transition-none duration-250 ease-out",
          visible ? "translate-x-0" : "translate-x-full",
        ].join(" ")}
        onClick={(e) => e.stopPropagation()}
        onTransitionEnd={handleTransitionEnd}
      >
        {/* ── Header (52px, sticky) ──────────────────────────────────────── */}
        <header className="sticky top-0 z-10 flex h-13 shrink-0 items-center justify-between gap-3 border-b border-border bg-surface px-4">
          {/* Esquerda: badge + título */}
          <div className="flex min-w-0 items-center gap-2">
            {badge && <span className="shrink-0">{badge}</span>}
            <h2
              id={titleId}
              ref={titleRef}
              // tabIndex={-1} torna um elemento não-interativo focalizável
              // via código (necessário para o comportamento de a11y ao abrir).
              tabIndex={-1}
              className="truncate text-sm font-semibold text-text outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface rounded-sm"
            >
              {title}
            </h2>
          </div>

          {/* Direita: ações + fechar */}
          <div className="flex shrink-0 items-center gap-2">
            {actions && <div className="flex items-center gap-2">{actions}</div>}
            <button
              type="button"
              aria-label="Fechar"
              onClick={onClose}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-text-muted transition-colors duration-120 hover:border-border hover:bg-surface-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
            >
              <XIcon className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* ── Breadcrumb (opcional) ──────────────────────────────────────── */}
        {breadcrumb && (
          <div className="shrink-0 border-b border-border bg-surface px-4 py-2 text-xs text-text-muted">
            {breadcrumb}
          </div>
        )}

        {/* ── Abas (opcional) ────────────────────────────────────────────── */}
        {tabs && (
          <div className="shrink-0 border-b border-border bg-surface">
            {tabs}
          </div>
        )}

        {/* ── Corpo scrollável ──────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>

        {/* ── Rodapé fixo (opcional) ────────────────────────────────────── */}
        {footer && (
          <div className="shrink-0 border-t border-border bg-surface px-4 py-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(panel, portalTarget);
}
