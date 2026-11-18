"use client";

import { useRef, useState } from "react";
import { FileText, X } from "lucide-react";
import { ApiError } from "@/app/lib/api";
import { idsDoAnexo, type CampoSolicitacao } from "@/app/lib/camposSolicitacao";
import {
  abrirDocumentoDemanda,
  DOCUMENTO_CONTENT_TYPE,
  DOCUMENTO_MAX_BYTES,
  enviarDocumentoDemanda,
  TIPO_ANEXO,
  type DocumentoDemanda,
} from "@/app/lib/solicitacoes";

/**
 * O que o campo de anexo precisa da solicitação em edição: a demanda dona dos
 * arquivos, o nome de cada documento já informado e o aviso de envio e de
 * retirada, para o formulário apagar o que subiu e não chegou a ser salvo.
 */
export type ContextoAnexo = {
  demandaId: number;
  nomes: Record<number, string>;
  onEnviado: (documento: DocumentoDemanda) => void;
  onRetirado: (documentoId: number) => void;
  /** Início e fim de um envio, para o formulário segurar Salvar e a troca de tipo. */
  onEnviando?: (ativo: boolean) => void;
  /**
   * O formulário está salvando: nada de enviar nem retirar arquivo. O payload já
   * foi montado, e o que mudasse agora não entraria nele.
   */
  bloqueado?: boolean;
};

type Props = {
  campo: CampoSolicitacao;
  valor: string;
  onChange: (valor: string) => void;
  error?: string;
  /** Sem contexto (a pré-visualização do catálogo), o campo aparece desabilitado. */
  contexto?: ContextoAnexo;
};

/**
 * Campo `format: anexo` de um tipo do catálogo (#365, PR #422). O arquivo sobe
 * na hora, pelo fluxo de documentos da demanda com `tipo="anexo"`, e o campo
 * guarda o id do documento; o backend liga o documento à solicitação ao salvar.
 * Só PDF, até 10 MB, como a aba Documentos.
 */
export function CampoAnexo({ campo, valor, onChange, error, contexto }: Props) {
  const id = `campo-${campo.chave}`;
  const arquivoRef = useRef<HTMLInputElement>(null);
  const [progresso, setProgresso] = useState<number | null>(null);
  const [erroLocal, setErroLocal] = useState<string | null>(null);

  const ids = idsDoAnexo(valor);
  const enviando = progresso !== null;
  const bloqueado = !!contexto?.bloqueado;
  const podeEnviar = !!contexto && !enviando && !bloqueado && (campo.multiplo || ids.length === 0);

  async function enviar(arquivo: File) {
    if (!contexto || !podeEnviar) return;
    if (arquivo.type !== DOCUMENTO_CONTENT_TYPE) return setErroLocal("Apenas PDF é aceito.");
    if (arquivo.size > DOCUMENTO_MAX_BYTES) return setErroLocal("O arquivo passa de 10 MB.");
    setErroLocal(null);
    setProgresso(0);
    contexto.onEnviando?.(true);
    try {
      const documento = await enviarDocumentoDemanda(
        contexto.demandaId,
        arquivo,
        { tipo: TIPO_ANEXO, descricao: "", fornecedor: "" },
        setProgresso,
      );
      contexto.onEnviado(documento);
      // `ids` é o de quando o envio começou: retirar fica bloqueado durante o
      // envio, então a lista não muda no meio e nada retirado volta (#426).
      onChange([...ids, documento.id].join(","));
    } catch (err) {
      setErroLocal(err instanceof ApiError ? err.message : "Não foi possível enviar o arquivo. Tente novamente.");
    } finally {
      setProgresso(null);
      contexto.onEnviando?.(false);
      if (arquivoRef.current) arquivoRef.current.value = "";
    }
  }

  function retirar(documentoId: number) {
    onChange(ids.filter((i) => i !== documentoId).join(","));
    contexto?.onRetirado(documentoId);
  }

  async function abrir(documentoId: number) {
    if (!contexto) return;
    try {
      await abrirDocumentoDemanda(contexto.demandaId, documentoId);
    } catch (err) {
      setErroLocal(err instanceof ApiError ? err.message : "Não foi possível abrir o arquivo.");
    }
  }

  const ajuda = [campo.ajuda, campo.multiplo ? "PDF, até 10 MB cada." : "PDF, até 10 MB."].filter(Boolean).join(" ");
  const mensagem = erroLocal ?? error;

  return (
    <div className="flex flex-col gap-1.5" data-testid={id}>
      <label htmlFor={id} className="text-sm font-medium text-text">
        {campo.rotulo}
        {campo.obrigatorio && <span className="text-error-text"> *</span>}
      </label>

      {ids.length > 0 && (
        <ul className="flex list-none flex-col gap-1.5">
          {ids.map((docId) => {
            const nome = contexto?.nomes[docId] ?? `Arquivo ${docId}`;
            return (
              <li
                key={docId}
                className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-1.5"
                data-testid={`${id}-arquivo-${docId}`}
              >
                <button
                  type="button"
                  onClick={() => void abrir(docId)}
                  className="flex min-w-0 items-center gap-2 text-left text-sm text-primary hover:underline"
                >
                  <FileText className="h-4 w-4 shrink-0" aria-hidden />
                  <span className="truncate">{nome}</span>
                </button>
                <button
                  type="button"
                  onClick={() => retirar(docId)}
                  disabled={enviando || bloqueado}
                  aria-label={`Retirar ${nome}`}
                  className="rounded p-1 text-text-muted hover:text-error-text disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {(campo.multiplo || ids.length === 0) && (
        <input
          ref={arquivoRef}
          id={id}
          type="file"
          accept={DOCUMENTO_CONTENT_TYPE}
          disabled={!podeEnviar}
          onChange={(e) => {
            const arquivo = e.target.files?.[0];
            if (arquivo) void enviar(arquivo);
          }}
          aria-invalid={!!mensagem}
          className="text-sm text-text file:mr-3 file:rounded-md file:border file:border-border file:bg-surface file:px-3 file:py-1.5 file:text-sm file:text-text disabled:opacity-60"
        />
      )}

      {progresso !== null && (
        <span role="status" className="text-xs text-text-muted">
          Enviando… {progresso}%
        </span>
      )}
      {contexto ? (
        <p className="text-xs text-text-muted">{ajuda}</p>
      ) : (
        <p className="text-xs text-text-muted">{ajuda} O arquivo é enviado ao preencher a solicitação na demanda.</p>
      )}
      {mensagem && <p className="text-xs text-error-text">{mensagem}</p>}
    </div>
  );
}
