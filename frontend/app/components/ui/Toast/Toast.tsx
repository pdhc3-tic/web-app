"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { CheckIcon, ErrorIcon, XIcon } from "@/app/components/icons";

export type ToastVariant = "success" | "error";

type ToastItem = {
  id: number;
  message: string;
  variant: ToastVariant;
};

type ToastContextValue = {
  /** Publica um toast. `error` permanece mais tempo em tela que `success`. */
  showToast: (message: string, variant?: ToastVariant) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const DISMISS_MS: Record<ToastVariant, number> = {
  success: 4000,
  error: 7000,
};

/**
 * Acesso ao toast. Requer <ToastProvider> acima na árvore — está montado no
 * layout de (protected), então qualquer tela autenticada pode usar.
 */
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast() precisa estar dentro de <ToastProvider>.");
  }
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [mounted, setMounted] = useState(false);
  const nextId = useRef(0);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  useEffect(() => {
    // O portal precisa do DOM, que só existe no client após o primeiro paint.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
    const pending = timers.current;
    return () => {
      for (const t of pending.values()) clearTimeout(t);
      pending.clear();
    };
  }, []);

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, variant: ToastVariant = "success") => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, message, variant }]);
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), DISMISS_MS[variant]),
      );
    },
    [dismiss],
  );

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {mounted &&
        createPortal(
          <ToastViewport toasts={toasts} onDismiss={dismiss} />,
          document.body,
        )}
    </ToastContext.Provider>
  );
}

function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
}) {
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2">
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

const VARIANT_CLASS: Record<ToastVariant, string> = {
  success: "border-success-text/30 bg-success-bg text-success-text",
  error: "border-error-text/30 bg-error-bg text-error-text",
};

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: ToastItem;
  onDismiss: (id: number) => void;
}) {
  const isError = toast.variant === "error";
  return (
    <div
      data-testid="toast"
      data-variant={toast.variant}
      // Erro interrompe o leitor de tela (assertive); sucesso apenas enfileira.
      role={isError ? "alert" : "status"}
      aria-live={isError ? "assertive" : "polite"}
      className={`pointer-events-auto flex items-start gap-2 rounded-lg border px-4 py-3 shadow-lg ${VARIANT_CLASS[toast.variant]}`}
    >
      <span className="mt-0.5 shrink-0">
        {isError ? <ErrorIcon /> : <CheckIcon className="h-3.5 w-3.5" />}
      </span>
      <p className="flex-1 text-sm leading-snug">{toast.message}</p>
      <button
        type="button"
        aria-label="Fechar aviso"
        onClick={() => onDismiss(toast.id)}
        className="-mr-1 -mt-1 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded opacity-70 hover:opacity-100"
      >
        <XIcon className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
