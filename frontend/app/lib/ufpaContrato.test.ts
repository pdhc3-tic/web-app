import { describe, expect, it } from "vitest";
import { caminhoBackendUfpa, contratoUfpa, nomeUfpa, respostaUfpa } from "./ufpaContrato";
import { nomeDoContentDisposition } from "./exportarPlano";

describe("contrato UFPA com o backend anterior a AJ-BE-09", () => {
  it("mantém rotas e filtros compatíveis sem alterar a busca livre", () => {
    expect(caminhoBackendUfpa("/api/v1/sgp/ufpas/7/membros/?q=ufpa&entidade=ufpa"))
      .toBe("/api/v1/sgp/upfs/7/membros/?q=ufpa&entidade=upf");
  });

  it("converte campos aninhados e discriminadores, preservando o conteúdo", () => {
    const backend = { results: [{ upf_id: 7, upfs_participantes: [7], tipo: "upfs", descricao: "UPF do José", total_upfs_produtoras: 2 }] };
    const frontend = { results: [{ ufpa_id: 7, ufpas_participantes: [7], tipo: "ufpas", descricao: "UPF do José", total_ufpas_produtoras: 2 }] };
    expect(contratoUfpa(backend)).toEqual(frontend);
    expect(contratoUfpa(frontend, true)).toEqual(backend);
    expect(contratoUfpa({ ufpa_documento_tipo: [] })).toEqual({ ufpa_documento_tipo: [] });
  });

  it("adapta o JSON de respostas reais sem consumir o stream de downloads", async () => {
    expect(await respostaUfpa(Response.json({ upf: 7, entidade: "upf" })).json())
      .toEqual({ ufpa: 7, entidade: "ufpa" });
    expect(await respostaUfpa(new Response("csv")).text()).toBe("csv");
  });

  it("apresenta erros e nomes de arquivos com o nome novo", () => {
    expect(contratoUfpa({ erro: "UPF indisponível", nome_arquivo: "upfs_2026.csv" }))
      .toEqual({ erro: "UFPA indisponível", nome_arquivo: "ufpas_2026.csv" });
    expect(contratoUfpa({ respostas_json: { upf: "valor original" } }))
      .toEqual({ respostas_json: { upf: "valor original" } });
    expect(nomeUfpa("UPF não encontrada; UPFs inacessíveis")).toBe("UFPA não encontrada; UFPAs inacessíveis");
    expect(nomeDoContentDisposition('attachment; filename="upfs_2026-11-12.csv"')).toBe("ufpas_2026-11-12.csv");
    expect(nomeDoContentDisposition("attachment; filename*=UTF-8''membros_upf_7.csv")).toBe("membros_ufpa_7.csv");
  });
});
