"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";

type CrudTabProps = {
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  /** Placeholder exibido enquanto o fetch está em andamento. */
  skeleton: React.ReactNode;
  children: React.ReactNode;
};

/**
 * Estrutura padrão de aba CRUD: exibe o skeleton durante o carregamento, a
 * seção de erro com botão "Tentar novamente" em caso de falha, ou o conteúdo
 * quando os dados chegaram.
 *
 * Use com `useFetch` — passe `loading`, `error` e `reload` diretamente.
 */
export function CrudTab({ loading, error, onRetry, skeleton, children }: CrudTabProps) {
  if (loading) return <>{skeleton}</>;
  if (error) return <TabErroSection message={error} onRetry={onRetry} />;
  return <>{children}</>;
}

export function TabErroSection({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
        <AlertTriangle className="h-6 w-6" />
      </span>
      <p className="max-w-sm text-sm text-text-muted">{message}</p>
      <Button variant="secondary" onClick={onRetry}>
        Tentar novamente
      </Button>
    </div>
  );
}
