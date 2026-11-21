import { beforeEach, describe, expect, it, vi } from "vitest";
import { criarSubmeta, payloadDaSubmeta, proximoNumeroDeSubmeta, validarSubmeta, type FormSubmeta } from "./submetas";

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", () => ({ apiClient: api.client }));

const META = { id: 9, numero: 3, data_inicio: "2026-01-01", data_fim: "2027-12-31" };

const valido: FormSubmeta = {
  numero: "3.1",
  titulo: "Formação de agentes",
  descricao: "",
  data_inicio: "2026-03-01",
  data_fim: "2026-12-31",
};

describe("proximoNumeroDeSubmeta (#431)", () => {
  it("sugere X.1 na primeira e o seguinte ao maior depois", () => {
    expect(proximoNumeroDeSubmeta(3, [])).toBe("3.1");
    expect(proximoNumeroDeSubmeta(3, [{ numero: "3.1" }, { numero: "3.10" }, { numero: "3.2" }])).toBe("3.11");
  });

  it("ignora números de outra Meta", () => {
    expect(proximoNumeroDeSubmeta(3, [{ numero: "31.4" }])).toBe("3.1");
  });
});

describe("validarSubmeta (#431): as regras de WorkPlanSubmeta.clean", () => {
  it("aceita o formulário válido", () => {
    expect(validarSubmeta(valido, META)).toEqual({});
  });

  it("número em X.Y e com o prefixo da Meta", () => {
    expect(validarSubmeta({ ...valido, numero: "" }, META).numero).toBe("Informe o número da Submeta.");
    expect(validarSubmeta({ ...valido, numero: "3.1.1" }, META).numero).toBe("Formato inválido. Use X.Y (ex: 1.1, 2.3).");
    expect(validarSubmeta({ ...valido, numero: "4.1" }, META).numero).toBe(
      "O número da Submeta deve começar com 3. (número da Meta).",
    );
  });

  it("título e datas obrigatórios, término depois do início", () => {
    const erros = validarSubmeta({ ...valido, titulo: " ", data_inicio: "", data_fim: "" }, META);
    expect(erros).toMatchObject({
      titulo: "Informe o título da Submeta.",
      data_inicio: "Informe a data de início.",
      data_fim: "Informe a data de término.",
    });
    expect(validarSubmeta({ ...valido, data_inicio: "2026-06-01", data_fim: "2026-05-01" }, META).data_fim).toBe(
      "A data de término não pode ser anterior à de início.",
    );
  });

  it("período contido no da Meta, com o erro na data que saiu dele", () => {
    const msg = "O período da Submeta deve estar contido no período da Meta (01/01/2026 a 31/12/2027).";
    expect(validarSubmeta({ ...valido, data_fim: "2028-01-31" }, META)).toEqual({ data_fim: msg });
    expect(validarSubmeta({ ...valido, data_inicio: "2025-12-01" }, META)).toEqual({ data_inicio: msg });
    expect(validarSubmeta({ ...valido, data_inicio: "2025-12-01", data_fim: "2028-01-31" }, META)).toEqual({
      data_inicio: msg,
      data_fim: msg,
    });
  });
});

describe("criarSubmeta", () => {
  beforeEach(() => api.client.mockReset());

  it("POST em /sgp/submetas/ com a Meta e os campos aparados", async () => {
    api.client.mockResolvedValue({ json: async () => ({ id: 1 }) });
    await criarSubmeta(payloadDaSubmeta({ ...valido, numero: " 3.1 ", titulo: " Formação " }, META.id));
    const [caminho, init] = api.client.mock.calls[0] as [string, RequestInit];
    expect(caminho).toBe("/api/v1/sgp/submetas/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      meta: 9,
      numero: "3.1",
      titulo: "Formação",
      descricao: "",
      data_inicio: "2026-03-01",
      data_fim: "2026-12-31",
    });
  });
});
