"use client";

import { useQuery } from "@tanstack/react-query";
import { Eye } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import {
  fetchPreviewArloMapping,
  type DirecaoArlo,
} from "@/app/lib/arloMapping";
import { qk } from "@/app/lib/queryKeys";

type Props = {
  direcao: DirecaoArlo;
};

/**
 * Preview da linha do CSV com o mapeamento vigente (#320, critério "Preview em
 * tempo real"), de `GET .../arlo-mapping/preview/?direcao=exportacao`. Criar,
 * editar, remover e reordenar invalidam esta query, então o preview acompanha
 * cada alteração.
 */
export function PreviewExportacao({ direcao }: Props) {
  const preview = useQuery({
    queryKey: qk.arloMapping.preview(direcao),
    queryFn: ({ signal }) => fetchPreviewArloMapping(direcao, signal),
    staleTime: 30_000,
  });

  if (preview.isPending) {
    return (
      <section
        aria-label="Preview da exportação"
        className="rounded-lg border border-border bg-surface p-4"
      >
        <div className="flex items-center gap-2 text-sm text-text-muted">
          <Spinner className="h-4 w-4 animate-spin" /> Carregando preview…
        </div>
      </section>
    );
  }

  if (preview.isError) {
    const mensagem =
      preview.error instanceof ApiError
        ? preview.error.message
        : "Não foi possível carregar o preview.";
    return (
      <section
        aria-label="Preview da exportação"
        className="rounded-lg border border-border bg-surface p-4 text-sm text-text-muted"
        data-testid="arlo-preview-erro"
      >
        {mensagem}
      </section>
    );
  }

  const dados = preview.data;

  if (!dados.colunas.length) {
    return (
      <section
        aria-label="Preview da exportação"
        className="rounded-lg border border-border bg-surface p-4 text-sm text-text-muted"
      >
        Nenhuma coluna ativa — adicione pelo menos um campo para ver o preview.
      </section>
    );
  }

  return (
    <section
      aria-label="Preview da exportação"
      className="rounded-lg border border-border bg-surface"
      data-testid="arlo-preview"
    >
      <header className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Eye className="h-4 w-4 text-text-muted" aria-hidden />
        <h3 className="text-sm font-medium text-text">
          Preview — linha do CSV com o mapeamento atual
        </h3>
      </header>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-surface-muted/50 text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <tr>
              {dados.colunas.map((c) => (
                <th key={c} className="px-3 py-2 whitespace-nowrap">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {dados.linha.map((v, i) => (
                <td key={i} className="px-3 py-2.5 whitespace-nowrap">
                  <span className="font-mono text-xs">
                    {v === "" ? "—" : v}
                  </span>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
