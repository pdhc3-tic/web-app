"use client";

import { useQuery } from "@tanstack/react-query";
import { Clock, Eye } from "lucide-react";
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
 * tempo real"). A rota `GET .../arlo-mapping/preview/?direcao=` é pendência
 * do backend (item 18 do doc da sprint 10, repetida no #373): enquanto não
 * existe, a tela mostra o aviso de pendência. Quando o backend responder, o
 * componente mostra a linha sem mudança: `fetchPreviewArloMapping` já
 * retorna `null` em 404.
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
      >
        {mensagem}
      </section>
    );
  }

  const dados = preview.data;

  if (dados === null) {
    // Rota ainda não existe no backend — explica a situação, sem travar a tela.
    return (
      <section
        aria-labelledby="preview-pendente-titulo"
        className="rounded-lg border border-dashed border-border bg-surface p-4"
        data-testid="arlo-preview-pendente"
      >
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-muted">
            <Clock className="h-4 w-4" aria-hidden />
          </span>
          <div className="flex-1 text-sm">
            <h3
              id="preview-pendente-titulo"
              className="font-medium text-text"
            >
              Preview aguardando o backend
            </h3>
            <p className="mt-1 text-text-muted">
              A rota que monta uma linha de exemplo da exportação com uma
              demanda real ainda não existe no backend. O pedido está registrado
              em <code className="font-mono text-xs">pendencias-backend-sprint-11.md</code>
              {" "}e na issue #373. Assim que a rota responder, o preview aparece
              aqui sem precisar mexer na tela.
            </p>
          </div>
        </div>
      </section>
    );
  }

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
                    {v === null ? "—" : String(v)}
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
