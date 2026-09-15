"use client";

import { Chip } from "@/app/components/ui/Chip/Chip";
import type { TecnicoListItem } from "@/app/lib/tecnicos";

type Props = {
  tecnicos: TecnicoListItem[];
  onSelect: (t: TecnicoListItem) => void;
};

export function TecnicosTable({ tecnicos, onSelect }: Props) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 z-10 bg-surface-muted">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-text-muted">Nome</th>
            <th className="px-4 py-3 text-left font-medium text-text-muted">Papel</th>
            <th className="hidden px-4 py-3 text-left font-medium text-text-muted md:table-cell">OSC</th>
            <th className="hidden px-4 py-3 text-left font-medium text-text-muted md:table-cell">Território</th>
            <th className="px-4 py-3 text-left font-medium text-text-muted">Situação</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-surface">
          {tecnicos.map((t) => (
            <tr
              key={t.id}
              className="cursor-pointer hover:bg-surface-muted"
              onClick={() => onSelect(t)}
            >
              <td className="px-4 py-3 font-medium text-text">{t.user_nome || "—"}</td>
              <td className="px-4 py-3 text-text-muted">{t.papel || "—"}</td>
              <td className="hidden px-4 py-3 text-text-muted md:table-cell">
                {t.osc_nome || "—"}
              </td>
              <td className="hidden px-4 py-3 md:table-cell">
                {t.territorio_nome ? (
                  <Chip>{t.territorio_nome}</Chip>
                ) : (
                  <span className="text-text-muted">—</span>
                )}
              </td>
              <td className="px-4 py-3">
                <Chip
                  className={
                    t.ativo
                      ? "border-success-text/30 bg-success-bg text-success-text"
                      : undefined
                  }
                >
                  {t.ativo ? "Ativo" : "Inativo"}
                </Chip>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
