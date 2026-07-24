import { apiClient } from "@/app/lib/api";

/** Camada de fluxo do upload de foto (BE-SGP-06): upload-url → PUT no storage → confirm. */

export type UploadUrlResponse = { url: string; key: string; expires_in: number };

/** POST {uploadUrlEndpoint} — pede a URL pré-assinada para o Blob final (pós-crop). */
export async function requestUploadUrl(
  endpoint: string,
  file: { name: string; type: string; size: number },
): Promise<UploadUrlResponse> {
  const res = await apiClient(endpoint, {
    method: "POST",
    body: JSON.stringify({
      filename: file.name,
      content_type: file.type,
      size: file.size,
    }),
  });
  return res.json();
}

/**
 * PUT direto no storage (R2 pré-assinado ou endpoint local) via XHR — usa XHR
 * (não fetch) para expor `upload.onprogress`. Sem header Authorization: a URL
 * já carrega sua própria autorização (assinatura).
 */
export function uploadToStorage(
  url: string,
  blob: Blob,
  contentType: string,
  onProgress: (percent: number) => void,
  signal?: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", contentType);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error("Falha ao enviar a imagem."));
    };
    xhr.onerror = () => reject(new Error("Falha de rede ao enviar a imagem."));
    xhr.onabort = () => reject(new DOMException("Upload cancelado.", "AbortError"));

    if (signal) {
      if (signal.aborted) {
        xhr.abort();
        return;
      }
      signal.addEventListener("abort", () => xhr.abort());
    }

    xhr.send(blob);
  });
}

/** POST {confirmEndpoint} — confirma que o objeto chegou ao storage. */
export async function confirmUpload(
  endpoint: string,
  key: string,
): Promise<{ foto_url: string }> {
  const res = await apiClient(endpoint, {
    method: "POST",
    body: JSON.stringify({ key }),
  });
  return res.json();
}

/** DELETE {deleteEndpoint} — remove a foto atual. */
export async function deletePhoto(endpoint: string): Promise<void> {
  await apiClient(endpoint, { method: "DELETE" });
}
