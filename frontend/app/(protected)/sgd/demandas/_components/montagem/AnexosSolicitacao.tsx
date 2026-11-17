"use client";

import { useState } from "react";
import { Paperclip } from "lucide-react";
import { ApiError } from "@/app/lib/api";
import { anexosDaSolicitacao, type SolicitacaoDemanda } from "@/app/lib/demandas";
import { useTiposSolicitacao } from "@/app/lib/hooks/useTiposSolicitacao";
import { abrirDocumentoDemanda } from "@/app/lib/solicitacoes";

/**
 * Os arquivos dos campos de anexo de uma solicitação (#365), campo a campo, com
 * o nome do campo do catálogo e o link que abre o arquivo. Nada aparece num tipo
 * sem anexo. Serve à montagem e ao painel da demanda.
 */
export function AnexosSolicitacao({ solicitacao }: { solicitacao: SolicitacaoDemanda }) {
  const catalogo = useTiposSolicitacao();
  const [erro, setErro] = useState<string | null>(null);
  const campos = anexosDaSolicitacao(solicitacao);
  if (campos.length === 0) return null;

  const propriedades = catalogo.data?.find((t) => t.slug === solicitacao.tipo)?.schema_campos?.properties ?? {};
  const rotulo = (campo: string) => propriedades[campo]?.title || campo;

  async function abrir(documentoId: number) {
    setErro(null);
    try {
      await abrirDocumentoDemanda(solicitacao.demanda, documentoId);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível abrir o arquivo.");
    }
  }

  return (
    <dl className="flex flex-col gap-1 text-xs" data-testid={`anexos-solicitacao-${solicitacao.id}`}>
      {campos.map(([campo, lista]) => (
        <div key={campo} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <dt className="text-text-muted">{rotulo(campo)}:</dt>
          {lista.map((anexo) => (
            <dd key={anexo.id}>
              <button
                type="button"
                onClick={() => void abrir(anexo.id)}
                className="inline-flex items-center gap-1 text-primary hover:underline"
                data-testid={`anexo-${anexo.id}`}
              >
                <Paperclip className="h-3.5 w-3.5 shrink-0" aria-hidden />
                {anexo.nome_original}
              </button>
            </dd>
          ))}
        </div>
      ))}
      {erro && (
        <p role="alert" className="text-error-text">
          {erro}
        </p>
      )}
    </dl>
  );
}
