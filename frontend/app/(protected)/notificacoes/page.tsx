import { Bell } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";

export default function NotificacoesPage() {
  return (
    <>
      <PageHeader>
        <h1 className="text-base font-semibold text-text truncate">Notificações</h1>
      </PageHeader>

      <div className="mx-auto flex max-w-2xl flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
        <span className="text-text-muted">
          <Bell className="h-10 w-10" aria-hidden="true" />
        </span>
        <h2 className="text-lg font-semibold text-text">
          Central de notificações
        </h2>
        <p className="max-w-md text-sm leading-relaxed text-text-muted">
          A listagem completa das suas notificações vai aparecer aqui em breve.
          Por enquanto, consulte as mais recentes pelo sino no topo da página.
        </p>
      </div>
    </>
  );
}
