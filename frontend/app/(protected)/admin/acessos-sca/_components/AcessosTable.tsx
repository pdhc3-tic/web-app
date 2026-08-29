"use client";

import { Badge } from "@/app/components/ui/Badge/Badge";
import { Avatar } from "@/app/components/ui/Avatar/Avatar";
import { Button } from "@/app/components/ui/Button/Button";
import { relativeTime, absoluteDateTime } from "@/app/lib/datetime";
import type { UserListItem } from "@/app/lib/users";

const TH_BASE =
  "sticky top-0 z-10 bg-surface-muted px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-[0.08em] text-text-muted whitespace-nowrap";

/**
 * O Badge não tem um status próprio para revogação, então o estado reusa a
 * paleta mais próxima com rótulo explícito: `nao-realizada` (vermelho, ícone de
 * X) para revogado e `ativo` (verde) para vigente. Vermelho e não neutro de
 * propósito — uma revogação é uma pendência de wipe, não um estado inerte.
 */
function AcessoCell({ user }: { user: UserListItem }) {
  if (!user.acesso_revogado) {
    return <Badge status="ativo" label="Vigente" />;
  }
  const quem = user.acesso_revogado_por?.nome;
  const quando = absoluteDateTime(user.acesso_revogado_em);
  const title = [
    quando ? `Revogado em ${quando}` : null,
    quem ? `por ${quem}` : null,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <span title={title || undefined}>
      <Badge status="nao-realizada" label="Revogado" />
    </span>
  );
}

type AcessosTableProps = {
  users: UserListItem[];
  loading: boolean;
  onRevogar: (user: UserListItem) => void;
  onReativar: (user: UserListItem) => void;
};

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 6 }).map((_, i) => (
        <tr key={i} className="border-t border-border">
          {Array.from({ length: 6 }).map((__, j) => (
            <td key={j} className="px-4 py-3">
              <div className="h-4 w-full max-w-[140px] animate-pulse rounded bg-surface-muted" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function AcessosTable({
  users,
  loading,
  onRevogar,
  onReativar,
}: AcessosTableProps) {
  return (
    <div className="relative max-h-[calc(100vh-22rem)] overflow-auto rounded-lg border border-border bg-surface">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className={TH_BASE}>Técnico</th>
            <th className={TH_BASE}>E-mail</th>
            <th className={TH_BASE}>Dispositivos</th>
            <th className={TH_BASE}>Último sync</th>
            <th className={TH_BASE}>Acesso</th>
            <th className={`${TH_BASE} text-right`}>Ações</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <SkeletonRows />
          ) : (
            users.map((u) => {
              const revogado = u.acesso_revogado;
              return (
                <tr
                  key={u.id}
                  data-testid={`acesso-row-${u.id}`}
                  data-revogado={String(revogado)}
                  className="border-t border-border transition-colors hover:bg-surface-muted"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar name={u.nome_completo} className="shadow-sm" />
                      <span className="font-medium text-text">
                        {u.nome_completo}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-text-muted">{u.email}</td>
                  <td className="px-4 py-3 text-text-muted">
                    {u.qtd_dispositivos ?? "—"}
                  </td>
                  <td
                    className="px-4 py-3 whitespace-nowrap text-text-muted"
                    title={absoluteDateTime(u.ultimo_sync_dispositivos)}
                  >
                    {u.ultimo_sync_dispositivos
                      ? relativeTime(u.ultimo_sync_dispositivos)
                      : "Nunca sincronizou"}
                  </td>
                  <td className="px-4 py-3">
                    <AcessoCell user={u} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    {revogado ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => onReativar(u)}
                        data-testid={`acesso-reativar-${u.id}`}
                      >
                        Reativar acesso
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => onRevogar(u)}
                        data-testid={`acesso-revogar-${u.id}`}
                      >
                        Revogar acesso
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
