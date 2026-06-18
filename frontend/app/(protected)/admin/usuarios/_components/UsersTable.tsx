"use client";

import { Badge } from "@/app/components/ui/Badge/Badge";
import { Avatar } from "@/app/components/ui/Avatar/Avatar";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { relativeTime, absoluteDateTime } from "@/app/lib/datetime";
import type { UserListItem } from "@/app/lib/users";
import type { Perfil, Territorio } from "@/app/lib/auth/types";

const TH_BASE =
  "sticky top-0 z-10 bg-surface-muted px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-[0.08em] text-text-muted whitespace-nowrap";

function PerfisCell({ perfis }: { perfis: Perfil[] }) {
  if (!perfis || perfis.length === 0) {
    return <span className="text-text-muted">—</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {perfis.map((p) => (
        <Chip key={p.id}>{p.nome}</Chip>
      ))}
    </div>
  );
}

function TerritoriosCell({ territorios }: { territorios: Territorio[] }) {
  if (!territorios || territorios.length === 0) {
    return <span className="text-text-muted">—</span>;
  }
  if (territorios.length <= 2) {
    return (
      <div className="flex flex-wrap gap-1">
        {territorios.map((t) => (
          <Chip key={t.id}>{t.nome}</Chip>
        ))}
      </div>
    );
  }
  const nomes = territorios.map((t) => t.nome).join(", ");
  return <Chip title={nomes}>Múltiplos ({territorios.length})</Chip>;
}

type UsersTableProps = {
  users: UserListItem[];
  selectedId: number | null;
  onSelect: (user: UserListItem) => void;
  loading: boolean;
};

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
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

export function UsersTable({
  users,
  selectedId,
  onSelect,
  loading,
}: UsersTableProps) {
  return (
    <div className="relative max-h-[calc(100vh-22rem)] overflow-auto rounded-lg border border-border bg-surface">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className={TH_BASE}>Nome</th>
            <th className={TH_BASE}>E-mail</th>
            <th className={TH_BASE}>Perfis</th>
            <th className={TH_BASE}>Territórios</th>
            <th className={TH_BASE}>Status</th>
            <th className={TH_BASE}>Último acesso</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <SkeletonRows />
          ) : (
            users.map((u) => {
              const selected = u.id === selectedId;
              return (
                <tr
                  key={u.id}
                  onClick={() => onSelect(u)}
                  aria-selected={selected}
                  className={`cursor-pointer border-t border-border transition-colors ${
                    selected ? "bg-success-bg" : "hover:bg-surface-muted"
                  }`}
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
                  <td className="px-4 py-3">
                    <PerfisCell perfis={u.perfis} />
                  </td>
                  <td className="px-4 py-3">
                    <TerritoriosCell territorios={u.territorios} />
                  </td>
                  <td className="px-4 py-3">
                    <Badge status={u.ativo ? "ativo" : "inativo"} />
                  </td>
                  <td
                    className="px-4 py-3 whitespace-nowrap text-text-muted"
                    title={absoluteDateTime(u.ultimo_login)}
                  >
                    {u.ultimo_login
                      ? relativeTime(u.ultimo_login)
                      : "Nunca acessou"}
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
