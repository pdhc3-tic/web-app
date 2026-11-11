import { describe, expect, it, vi } from "vitest";
import {
  PARAMETROS,
  fetchConfigs,
  paraBooleano,
  salvarConfig,
  validarParametro,
  valorDeTela,
  type ChaveParametro,
  type DefinicaoParametro,
} from "@/app/lib/parametrosOrcamento";

/** #403: parâmetros globais do orçamento, com validação de tipo e de faixa. */

const api = vi.hoisted(() => ({ client: vi.fn() }));
vi.mock("@/app/lib/api", () => ({ apiClient: api.client }));

const def = (chave: ChaveParametro): DefinicaoParametro => PARAMETROS.find((p) => p.chave === chave)!;

describe("PARAMETROS", () => {
  it("cobre as seis chaves da issue", () => {
    expect(PARAMETROS.map((p) => p.chave)).toEqual([
      "budget_limit_period",
      "budget_limit_carry_over",
      "budget_overallocation_allowed",
      "budget_subexec_alert_months",
      "budget_subexec_min_pct",
      "budget_transfer_alert_pct",
    ]);
  });
});

describe("validarParametro", () => {
  it("periodicidade: só as opções do backend", () => {
    expect(validarParametro(def("budget_limit_period"), "trimestral")).toBeNull();
    expect(validarParametro(def("budget_limit_period"), "anual")).toBe("Escolha uma das opções.");
  });

  it("booleano: só true ou false", () => {
    expect(validarParametro(def("budget_limit_carry_over"), "true")).toBeNull();
    expect(validarParametro(def("budget_overallocation_allowed"), "false")).toBeNull();
    expect(validarParametro(def("budget_limit_carry_over"), "sim")).toBe("Valor inválido.");
  });

  it("inteiro: recusa texto, decimal e negativo", () => {
    const meses = def("budget_subexec_alert_months");
    expect(validarParametro(meses, "abc")).toBe("Informe um número inteiro.");
    expect(validarParametro(meses, "2.5")).toBe("Informe um número inteiro.");
    expect(validarParametro(meses, "-1")).toBe("Informe um número inteiro.");
    expect(validarParametro(meses, "")).toBe("Informe um número inteiro.");
  });

  it("inteiro: confere a faixa de cada parâmetro", () => {
    expect(validarParametro(def("budget_subexec_alert_months"), "6")).toBeNull();
    expect(validarParametro(def("budget_subexec_alert_months"), "0")).toBe("Informe um valor entre 1 e 24.");
    expect(validarParametro(def("budget_subexec_alert_months"), "25")).toBe("Informe um valor entre 1 e 24.");
    expect(validarParametro(def("budget_subexec_min_pct"), "100")).toBeNull();
    expect(validarParametro(def("budget_subexec_min_pct"), "101")).toBe("Informe um valor entre 1 e 100.");
    expect(validarParametro(def("budget_transfer_alert_pct"), "25")).toBeNull();
    expect(validarParametro(def("budget_transfer_alert_pct"), "0")).toBe("Informe um valor entre 1 e 100.");
  });
});

describe("valores do backend", () => {
  it("lê o booleano gravado como texto", () => {
    expect(paraBooleano("True")).toBe(true);
    expect(paraBooleano("1")).toBe(true);
    expect(paraBooleano("False")).toBe(false);
    expect(paraBooleano(undefined)).toBe(false);
    expect(valorDeTela(def("budget_limit_carry_over"), "True")).toBe("true");
    expect(valorDeTela(def("budget_subexec_min_pct"), " 60 ")).toBe("60");
  });
});

describe("API", () => {
  it("lista com teto alto e aceita resposta paginada ou não", async () => {
    api.client.mockResolvedValue({ json: async () => ({ count: 1, results: [{ chave: "a" }] }) });
    expect(await fetchConfigs()).toEqual([{ chave: "a" }]);
    expect(api.client.mock.calls.at(-1)?.[0]).toBe("/api/v1/system-config/?limit=200");
    api.client.mockResolvedValue({ json: async () => [{ chave: "b" }] });
    expect(await fetchConfigs()).toEqual([{ chave: "b" }]);
  });

  it("salva com PATCH só do valor", async () => {
    api.client.mockResolvedValue({ json: async () => ({}) });
    await salvarConfig("budget_subexec_min_pct", "70");
    const [path, init] = api.client.mock.calls.at(-1) as [string, RequestInit];
    expect(path).toBe("/api/v1/system-config/budget_subexec_min_pct/");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ valor: "70" });
  });
});
