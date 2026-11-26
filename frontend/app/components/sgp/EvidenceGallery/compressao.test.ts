import { describe, expect, it, vi } from "vitest";
import { comprimirFoto, nomeJpg, planoDeTentativas, type Dependencias, type Tentativa } from "./compressao";

const LIMITE = 819_200;

function arquivo(tamanho: number, nome = "foto.png", tipo = "image/png"): File {
  return new File([new Uint8Array(tamanho)], nome, { type: tipo, lastModified: 1_700_000_000_000 });
}

/** Codificador falso: o tamanho do JPEG vem de uma função da tentativa. */
function deps(tamanhoDe: (t: Tentativa) => number, largura = 4000, altura = 3000) {
  const liberar = vi.fn();
  const codificar = vi.fn(async (_img: unknown, t: Tentativa) => new Blob([new Uint8Array(tamanhoDe(t))]));
  const d: Dependencias = { carregar: async () => ({ largura, altura, liberar }), codificar };
  return { d, codificar, liberar };
}

describe("planoDeTentativas (#464)", () => {
  it("começa no maior lado permitido, sem ampliar, e desce qualidade antes da resolução", () => {
    const plano = planoDeTentativas(4000, 3000);
    expect(plano[0]).toEqual({ largura: 2560, altura: 1920, qualidade: 0.85 });
    expect(plano.slice(0, 4).map((t) => t.qualidade)).toEqual([0.85, 0.75, 0.65, 0.55]);
    expect(plano[4]).toEqual({ largura: 1920, altura: 1440, qualidade: 0.85 });
    expect(plano.at(-1)).toEqual({ largura: 800, altura: 600, qualidade: 0.55 });
  });

  it("imagem menor que 2560 começa no tamanho dela", () => {
    const plano = planoDeTentativas(1000, 1500);
    expect(plano[0]).toEqual({ largura: 1000, altura: 1500, qualidade: 0.85 });
    expect(Math.max(plano.at(-1)!.largura, plano.at(-1)!.altura)).toBe(800);
  });
});

describe("comprimirFoto (#464)", () => {
  it("foto dentro do limite vai como veio, sem redesenhar", async () => {
    const { d, codificar } = deps(() => 1);
    const original = arquivo(LIMITE);
    const r = await comprimirFoto(original, LIMITE, d);
    expect(r).toEqual({ ok: true, arquivo: original, comprimida: false });
    expect(codificar).not.toHaveBeenCalled();
  });

  it("acima do limite, devolve o primeiro JPEG que cabe, com nome .jpg", async () => {
    // Só cabe a partir da segunda resolução, na qualidade 0,65.
    const { d, codificar, liberar } = deps((t) => (t.largura <= 1920 && t.qualidade <= 0.65 ? 700_000 : 2_000_000));
    const r = await comprimirFoto(arquivo(3_000_000, "IMG_0001.PNG"), LIMITE, d);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.comprimida).toBe(true);
    expect(r.arquivo.size).toBe(700_000);
    expect(r.arquivo.type).toBe("image/jpeg");
    expect(r.arquivo.name).toBe("IMG_0001.jpg");
    expect(codificar).toHaveBeenCalledTimes(7);
    expect(liberar).toHaveBeenCalledOnce();
  });

  it("se nenhuma tentativa couber, recusa com o motivo", async () => {
    const { d, liberar } = deps(() => 5_000_000);
    expect(await comprimirFoto(arquivo(3_000_000), LIMITE, d)).toEqual({ ok: false, motivo: "grande_demais" });
    expect(liberar).toHaveBeenCalledOnce();
  });

  it("imagem que o navegador não lê vira motivo ilegível", async () => {
    const d: Dependencias = {
      carregar: async () => {
        throw new Error("corrompida");
      },
      codificar: vi.fn(),
    };
    expect(await comprimirFoto(arquivo(3_000_000), LIMITE, d)).toEqual({ ok: false, motivo: "ilegivel" });
  });

  it("nomeJpg troca só a extensão", () => {
    expect(nomeJpg("viagem.final.webp")).toBe("viagem.final.jpg");
    expect(nomeJpg("semextensao")).toBe("semextensao.jpg");
  });
});
