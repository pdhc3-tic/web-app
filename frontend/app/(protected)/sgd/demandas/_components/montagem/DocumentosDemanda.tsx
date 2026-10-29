"use client";

import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Paperclip, Trash2 } from "lucide-react";
import { ConfirmDeleteDialog } from "@/app/components/ui/ConfirmDeleteDialog/ConfirmDeleteDialog";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { ApiError } from "@/app/lib/api";
import { qk } from "@/app/lib/queryKeys";
import {
  abrirDocumentoDemanda,
  DOCUMENTO_CONTENT_TYPE,
  DOCUMENTO_MAX_BYTES,
  DOCUMENTOS_POR_DEMANDA,
  enviarDocumentoDemanda,
  listDocumentosDemanda,
  removerDocumentoDemanda,
  type DocumentoDemanda,
} from "@/app/lib/solicitacoes";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";

/** Comprovante é da FGD, no atendimento (`TIPOS_FGD` em `services/demand_document.py`). */
const TIPO_SO_DA_FGD = "comprovante";
const COTACAO = "cotacao";

function tamanho(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`;
}

export function useDocumentosDemanda(demandaId: number) {
  return useQuery({
    queryKey: qk.demandas.documentos(demandaId),
    queryFn: ({ signal }) => listDocumentosDemanda(demandaId, signal),
  });
}

/**
 * Documentos de suporte da demanda (#295): TDR, cronograma e as cotações que
 * a Aquisição de Equipamentos exige (§3.6). Só PDF, até 10 MB, até 10 por
 * demanda — os limites de `views/demand_document.py`, conferidos antes do envio.
 */
export function DocumentosDemanda({ demandaId }: { demandaId: number }) {
  const queryClient = useQueryClient();
  const choices = useSgpChoices();
  const documentos = useDocumentosDemanda(demandaId);
  const arquivoRef = useRef<HTMLInputElement>(null);

  const [tipo, setTipo] = useState("");
  const [descricao, setDescricao] = useState("");
  const [fornecedor, setFornecedor] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [progresso, setProgresso] = useState<number | null>(null);
  const [removendo, setRemovendo] = useState<DocumentoDemanda | null>(null);

  const lista = documentos.data ?? [];
  const cheio = lista.length >= DOCUMENTOS_POR_DEMANDA;

  function limpar() {
    setTipo("");
    setDescricao("");
    setFornecedor("");
    setArquivo(null);
    if (arquivoRef.current) arquivoRef.current.value = "";
  }

  async function anexar() {
    const e: Record<string, string> = {};
    if (!tipo) e.tipo = "Escolha o tipo do documento.";
    if (tipo === COTACAO && !fornecedor.trim()) e.fornecedor = "Informe o fornecedor da cotação.";
    if (!arquivo) e.arquivo = "Escolha o arquivo.";
    else if (arquivo.type !== DOCUMENTO_CONTENT_TYPE) e.arquivo = "Apenas PDF é aceito.";
    else if (arquivo.size > DOCUMENTO_MAX_BYTES) e.arquivo = "O arquivo passa de 10 MB.";
    setErros(e);
    setErroGeral(null);
    if (Object.keys(e).length > 0 || !arquivo) return;

    setProgresso(0);
    try {
      await enviarDocumentoDemanda(
        demandaId,
        arquivo,
        { tipo, descricao: descricao.trim(), fornecedor: tipo === COTACAO ? fornecedor.trim() : "" },
        setProgresso,
      );
      limpar();
      await queryClient.invalidateQueries({ queryKey: qk.demandas.documentos(demandaId) });
    } catch (err) {
      setErroGeral(err instanceof ApiError ? err.message : "Não foi possível anexar o documento.");
    } finally {
      setProgresso(null);
    }
  }

  async function abrir(doc: DocumentoDemanda) {
    try {
      await abrirDocumentoDemanda(demandaId, doc.id);
    } catch (err) {
      setErroGeral(err instanceof ApiError ? err.message : "Não foi possível abrir o documento.");
    }
  }

  return (
    <section className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-6" data-testid="documentos-demanda">
      <div>
        <h2 className="text-base font-semibold text-text">Documentos</h2>
        <p className="mt-0.5 text-sm text-text-muted">
          TDR, cronograma e cotações. Só PDF, até 10 MB, até {DOCUMENTOS_POR_DEMANDA} por demanda.
        </p>
      </div>

      {documentos.isPending ? (
        <p className="text-sm text-text-muted">Carregando os documentos…</p>
      ) : documentos.isError ? (
        <p role="alert" className="text-sm text-error-text">
          {documentos.error instanceof ApiError ? documentos.error.message : "Não foi possível carregar os documentos."}
        </p>
      ) : lista.length === 0 ? (
        <p className="text-sm text-text-muted">Nenhum documento anexado.</p>
      ) : (
        <ul className="flex list-none flex-col gap-2" data-testid="documentos-lista">
          {lista.map((doc) => (
            <li
              key={doc.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2"
              data-testid={`documento-${doc.id}`}
            >
              <button
                type="button"
                onClick={() => void abrir(doc)}
                className="flex min-w-0 items-center gap-2 text-left text-sm text-primary hover:underline"
              >
                <FileText className="h-4 w-4 shrink-0" aria-hidden />
                <span className="truncate">{doc.nome_original}</span>
              </button>
              <span className="flex items-center gap-3 text-xs text-text-muted">
                <span>
                  {doc.tipo_display}
                  {doc.fornecedor && ` · ${doc.fornecedor}`}
                  {doc.descricao && ` · ${doc.descricao}`} · {tamanho(doc.tamanho_bytes)}
                </span>
                <button
                  type="button"
                  onClick={() => setRemovendo(doc)}
                  aria-label={`Remover ${doc.nome_original}`}
                  className="rounded p-1 text-text-muted hover:text-error-text"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {cheio ? (
        <p className="text-sm text-text-muted">Limite de {DOCUMENTOS_POR_DEMANDA} documentos atingido.</p>
      ) : (
        <div className="grid gap-4 border-t border-border pt-4 sm:grid-cols-2" data-testid="documento-novo">
          <Select
            id="documento-tipo"
            label="Tipo do documento"
            required
            options={choices.demanda_documento_tipo.filter((op) => op.value !== TIPO_SO_DA_FGD)}
            value={tipo}
            onChange={(v) => {
              setTipo(v);
              setErros({});
            }}
            error={erros.tipo}
            name="documento_tipo"
          />
          {tipo === COTACAO ? (
            <Input
              id="documento-fornecedor"
              label="Fornecedor"
              required
              value={fornecedor}
              onChange={(e) => setFornecedor(e.target.value)}
              error={erros.fornecedor}
            />
          ) : (
            <Input
              id="documento-descricao"
              label="Descrição"
              placeholder="Ex.: TDR, cronograma"
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
            />
          )}
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <label htmlFor="documento-arquivo" className="text-sm font-medium text-text">
              Arquivo (PDF) <span className="text-error-text">*</span>
            </label>
            <input
              ref={arquivoRef}
              id="documento-arquivo"
              type="file"
              accept={DOCUMENTO_CONTENT_TYPE}
              onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
              className="text-sm text-text file:mr-3 file:rounded-md file:border file:border-border file:bg-surface file:px-3 file:py-1.5 file:text-sm file:text-text"
            />
            {erros.arquivo && <p className="text-xs text-error-text">{erros.arquivo}</p>}
          </div>
          <div className="flex items-center justify-end gap-3 sm:col-span-2">
            {progresso !== null && (
              <span role="status" className="text-xs text-text-muted">
                Enviando… {progresso}%
              </span>
            )}
            <Button
              variant="secondary"
              leftIcon={<Paperclip className="h-4 w-4" />}
              onClick={anexar}
              loading={progresso !== null}
              data-testid="documento-anexar"
            >
              Anexar documento
            </Button>
          </div>
        </div>
      )}

      {erroGeral && (
        <p role="alert" className="text-sm text-error-text" data-testid="documentos-erro">
          {erroGeral}
        </p>
      )}

      <ConfirmDeleteDialog
        open={removendo !== null}
        onClose={() => setRemovendo(null)}
        title="Remover documento"
        itemName={removendo?.nome_original ?? ""}
        onConfirm={async () => {
          if (!removendo) return;
          await removerDocumentoDemanda(demandaId, removendo.id);
          setRemovendo(null);
          await queryClient.invalidateQueries({ queryKey: qk.demandas.documentos(demandaId) });
        }}
      />
    </section>
  );
}
