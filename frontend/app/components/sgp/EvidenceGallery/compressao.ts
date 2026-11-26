/**
 * Compressão automática da foto de evidência para caber no limite do backend
 * (800 KB, `MAX_PHOTO_SIZE_BYTES`), como pede a DRS 3.3 (#464).
 *
 * Foto que já cabe vai como veio. Acima do limite, o navegador redesenha a
 * imagem num canvas e gera um JPEG: primeiro baixa a qualidade, depois a
 * resolução, até caber. A orientação da câmera é aplicada na leitura, e PNG
 * com transparência ganha fundo branco (o JPEG não tem canal alfa).
 *
 * O JPEG gerado não leva o EXIF da original. Hoje nada se perde: nem o front
 * nem o backend leem o EXIF (a data de captura é a hora do upload).
 */
import { PHOTO_MAX_SIZE_BYTES } from "./types";

/** Maior lado, em pixels, de cada rodada. Acima de 2560 não há ganho para evidência. */
const LADOS = [2560, 1920, 1600, 1280, 1024, 800];
const QUALIDADES = [0.85, 0.75, 0.65, 0.55];

export type Tentativa = { largura: number; altura: number; qualidade: number };

/**
 * Ordem das tentativas para uma imagem `largura × altura`: em cada lado
 * máximo (sem ampliar a original), todas as qualidades, da maior para a menor.
 */
export function planoDeTentativas(largura: number, altura: number): Tentativa[] {
  const maior = Math.max(largura, altura);
  const lados = [...new Set([Math.min(maior, LADOS[0]), ...LADOS.filter((l) => l < maior)])];
  return lados.flatMap((lado) => {
    const escala = lado / maior;
    const w = Math.max(1, Math.round(largura * escala));
    const h = Math.max(1, Math.round(altura * escala));
    return QUALIDADES.map((qualidade) => ({ largura: w, altura: h, qualidade }));
  });
}

export type Imagem = { largura: number; altura: number; liberar?: () => void };

export type Dependencias = {
  /** Lê a imagem já na orientação da câmera. */
  carregar: (arquivo: File) => Promise<Imagem>;
  /** Gera o JPEG da tentativa. */
  codificar: (imagem: Imagem, tentativa: Tentativa) => Promise<Blob>;
};

export type ResultadoCompressao =
  | { ok: true; arquivo: File; comprimida: boolean }
  | { ok: false; motivo: "ilegivel" | "grande_demais" };

/** Nome do arquivo com a extensão trocada por `.jpg`. */
export function nomeJpg(nome: string): string {
  const base = nome.replace(/\.[^./\\]+$/, "");
  return `${base || "foto"}.jpg`;
}

export async function comprimirFoto(
  arquivo: File,
  limite: number = PHOTO_MAX_SIZE_BYTES,
  deps: Dependencias = DEPENDENCIAS_DO_NAVEGADOR,
): Promise<ResultadoCompressao> {
  if (arquivo.size <= limite) return { ok: true, arquivo, comprimida: false };

  let imagem: Imagem;
  try {
    imagem = await deps.carregar(arquivo);
  } catch {
    return { ok: false, motivo: "ilegivel" };
  }

  try {
    for (const tentativa of planoDeTentativas(imagem.largura, imagem.altura)) {
      const blob = await deps.codificar(imagem, tentativa);
      if (blob.size <= limite) {
        const comprimido = new File([blob], nomeJpg(arquivo.name), {
          type: "image/jpeg",
          lastModified: arquivo.lastModified,
        });
        return { ok: true, arquivo: comprimido, comprimida: true };
      }
    }
    return { ok: false, motivo: "grande_demais" };
  } catch {
    return { ok: false, motivo: "ilegivel" };
  } finally {
    imagem.liberar?.();
  }
}

// ─── Implementação do navegador ──────────────────────────────────────────────

type ImagemDoNavegador = Imagem & { bitmap: ImageBitmap };

const DEPENDENCIAS_DO_NAVEGADOR: Dependencias = {
  async carregar(arquivo) {
    const bitmap = await createImageBitmap(arquivo, { imageOrientation: "from-image" });
    const imagem: ImagemDoNavegador = {
      bitmap,
      largura: bitmap.width,
      altura: bitmap.height,
      liberar: () => bitmap.close(),
    };
    return imagem;
  },
  codificar(imagem, { largura, altura, qualidade }) {
    const { bitmap } = imagem as ImagemDoNavegador;
    const canvas = document.createElement("canvas");
    canvas.width = largura;
    canvas.height = altura;
    const ctx = canvas.getContext("2d");
    if (!ctx) return Promise.reject(new Error("canvas indisponível"));
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, largura, altura);
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(bitmap, 0, 0, largura, altura);
    return new Promise((resolve, reject) =>
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error("falha ao gerar o JPEG"))),
        "image/jpeg",
        qualidade,
      ),
    );
  },
};
