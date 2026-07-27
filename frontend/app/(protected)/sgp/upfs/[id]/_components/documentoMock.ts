import type { Documento, DocumentoWritePayload } from "./documentoTypes";

const STORE = new Map<string, Documento[]>();
let NEXT_ID = 5000;

function seedFor(): Documento[] {
  const now = Date.now();
  return [
    {
      id: NEXT_ID++,
      tipo: "dap_caf",
      descricao: "DAP emitida em 2024, válida por 2 anos.",
      nome_original: "dap_2024.pdf",
      content_type: "application/pdf",
      tamanho_bytes: 245_760,
      data_documento: "2024-03-15",
      criado_em: new Date(now - 3 * 24 * 60 * 60 * 1000).toISOString(),
      criado_por: "Maria Silva",
    },
    {
      id: NEXT_ID++,
      tipo: "contrato",
      descricao: "Contrato de comodato — 3ha.",
      nome_original: "contrato_comodato.pdf",
      content_type: "application/pdf",
      tamanho_bytes: 1_258_291,
      data_documento: "2025-01-10",
      criado_em: new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString(),
      criado_por: "João Pereira",
    },
    {
      id: NEXT_ID++,
      tipo: "identidade",
      descricao: "RG do titular (frente).",
      nome_original: "rg_frente.jpg",
      content_type: "image/jpeg",
      tamanho_bytes: 512_000,
      data_documento: "2020-08-22",
      criado_em: new Date(now - 2 * 60 * 60 * 1000).toISOString(),
      criado_por: "Maria Silva",
    },
  ];
}

function ensure(upfId: string): Documento[] {
  const key = String(upfId);
  if (!STORE.has(key)) STORE.set(key, seedFor());
  return STORE.get(key)!;
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function listDocumentosMock(upfId: string, signal?: AbortSignal) {
  await delay(350);
  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
  return [...ensure(upfId)];
}

export async function deleteDocumentoMock(upfId: string, id: number): Promise<void> {
  await delay(300);
  const list = ensure(upfId);
  const idx = list.findIndex((d) => d.id === id);
  if (idx === -1) throw new Error("Documento não encontrado.");
  list.splice(idx, 1);
}

export type UploadHandle = {
  promise: Promise<Documento>;
  abort: () => void;
};

export function uploadDocumentoMock(
  upfId: string,
  file: File,
  payload: Omit<DocumentoWritePayload, "nome_original" | "content_type" | "tamanho_bytes">,
  onProgress: (percent: number) => void,
): UploadHandle {
  let aborted = false;
  let intervalId: ReturnType<typeof setInterval> | null = null;

  const promise = new Promise<Documento>((resolve, reject) => {
    let percent = 0;
    intervalId = setInterval(() => {
      if (aborted) {
        if (intervalId) clearInterval(intervalId);
        reject(new DOMException("Upload cancelado.", "AbortError"));
        return;
      }
      percent = Math.min(100, percent + Math.random() * 18 + 5);
      onProgress(Math.round(percent));
      if (percent >= 100) {
        if (intervalId) clearInterval(intervalId);
        const saved: Documento = {
          id: NEXT_ID++,
          tipo: payload.tipo,
          descricao: payload.descricao,
          nome_original: file.name,
          content_type: file.type,
          tamanho_bytes: file.size,
          data_documento: payload.data_documento,
          criado_em: new Date().toISOString(),
          criado_por: "Você",
        };
        ensure(upfId).unshift(saved);
        setTimeout(() => resolve(saved), 200);
      }
    }, 180);
  });

  return {
    promise,
    abort: () => {
      aborted = true;
      if (intervalId) clearInterval(intervalId);
    },
  };
}

export function downloadDocumentoMock(doc: Documento): void {
  const blob = new Blob(
    [`Mock — ${doc.nome_original}\nTipo: ${doc.content_type}\nTamanho: ${doc.tamanho_bytes} bytes`],
    { type: "text/plain" },
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = doc.nome_original;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
