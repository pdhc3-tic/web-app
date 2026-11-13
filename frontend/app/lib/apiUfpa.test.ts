import { afterEach, describe, expect, it, vi } from "vitest";
vi.mock("next-auth/react", () => ({
  getSession: vi.fn(async () => ({ accessToken: "token" })),
  signIn: vi.fn(), signOut: vi.fn(),
}));
import { apiClient } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("integração UFPA no cliente autenticado", () => {
  it("envia o contrato aceito pelo serializer e entrega os tipos da interface", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ upfs_participantes: [{ id: 7 }], descricao: "UPF original" }));
    vi.stubGlobal("fetch", fetch);
    const res = await apiClient("/api/v1/sgp/ufpas/7/", { method: "PATCH", body: JSON.stringify({ ufpas_participantes: [7], descricao: "UPF original" }) });
    expect(fetch.mock.calls[0][0]).toMatch(/\/api\/v1\/sgp\/upfs\/7\/$/);
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ upfs_participantes: [7], descricao: "UPF original" });
    expect(await res.json()).toEqual({ ufpas_participantes: [{ id: 7 }], descricao: "UPF original" });
  });

  it("aplica a mesma compatibilidade depois de renovar o token", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(Response.json({ upf: 7 }));
    vi.stubGlobal("fetch", fetch);
    expect(await (await apiClient("/api/v1/sgp/ufpas/7/")).json()).toEqual({ ufpa: 7 });
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("exibe o nome novo nos erros recebidos do backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "UPF não encontrada." }, { status: 404 })));
    await expect(apiClient("/api/v1/sgp/ufpas/7/")).rejects.toMatchObject({ message: "UFPA não encontrada." });
  });
});
