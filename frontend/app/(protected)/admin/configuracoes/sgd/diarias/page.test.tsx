import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import type { FaixaDestino, ParametrosDiarias, ValorDiaria } from "@/app/lib/diarias";
import TabelaDiariasPage from "./page";

/** #366 — tela de configuração da tabela de diárias (Super Admin e FGD). */

const mocks = vi.hoisted(() => ({
  perfis: ["fgd"] as string[],
  showToast: vi.fn(),
  listarFaixas: vi.fn(),
  listarValores: vi.fn(),
  lerParametros: vi.fn(),
  criarValor: vi.fn(),
  registrarNovaVigencia: vi.fn(),
  excluirValor: vi.fn(),
  salvarEnquadramentos: vi.fn(),
  salvarParametros: vi.fn(),
}));

vi.mock("next-auth/react", () => ({
  useSession: () => ({
    status: "authenticated",
    data: { user: { perfis: mocks.perfis.map((slug) => ({ perfil: { slug } })) } },
  }),
}));

vi.mock("@/app/lib/auth/roles", async (original) => {
  const atual = await original<typeof import("@/app/lib/auth/roles")>();
  const tem = (slug: string) => mocks.perfis.includes(slug);
  return {
    ...atual,
    isSuperAdmin: () => tem("super-admin"),
    canConfigurarDiarias: () => tem("super-admin") || tem("fgd"),
  };
});

vi.mock("@/app/components/layout/PageHeader", () => ({
  PageHeader: ({ children }: { children: React.ReactNode }) => <header>{children}</header>,
}));

vi.mock("@/app/components/ui/Toast/Toast", () => ({ useToast: () => ({ showToast: mocks.showToast }) }));

// O Select e a busca do design system abrem listas próprias; no teste, controles nativos.
vi.mock("@/app/components/ui/Select/Select", () => ({
  Select: ({
    id,
    options,
    value,
    onChange,
  }: {
    id: string;
    options: { value: string; label: string }[];
    value: string;
    onChange: (v: string) => void;
  }) => (
    <select data-testid={id} value={value} onChange={(e) => onChange(e.target.value)}>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  ),
}));

const NATAL = { codigo_ibge: "2408102", nome_referencia: "Natal" };

vi.mock("@/app/components/ui/SearchSelect/SearchSelect", () => ({
  SearchSelect: ({
    onChange,
    "data-testid": testId,
  }: {
    onChange: (o: { value: string; label: string; item: typeof NATAL }) => void;
    "data-testid"?: string;
  }) => (
    <button type="button" data-testid={testId} onClick={() => onChange({ value: NATAL.codigo_ibge, label: "Natal", item: NATAL })}>
      Adicionar Natal
    </button>
  ),
}));

vi.mock("@/app/lib/diarias", async (original) => ({
  ...(await original<typeof import("@/app/lib/diarias")>()),
  listarFaixas: mocks.listarFaixas,
  listarValores: mocks.listarValores,
  lerParametros: mocks.lerParametros,
  criarValor: mocks.criarValor,
  registrarNovaVigencia: mocks.registrarNovaVigencia,
  excluirValor: mocks.excluirValor,
  salvarEnquadramentos: mocks.salvarEnquadramentos,
  salvarParametros: mocks.salvarParametros,
}));

const FAIXAS: FaixaDestino[] = [
  {
    id: 1,
    nome: "Brasília, Manaus e Rio de Janeiro",
    ordem: 1,
    padrao: null,
    ativo: true,
    enquadramentos: [{ codigo_ibge: "5300108", nome_referencia: "Brasília" }],
  },
  { id: 2, nome: "Demais localidades", ordem: 2, padrao: "demais", ativo: true, enquadramentos: [] },
  { id: 3, nome: "Exterior", ordem: 3, padrao: null, ativo: true, enquadramentos: [] },
];

function valor(id: number, faixa: number, inicio: string, fim: string | null, quanto: string, origem: ValorDiaria["origem"]): ValorDiaria {
  return {
    id,
    faixa_destino: faixa,
    faixa_destino_nome: FAIXAS.find((f) => f.id === faixa)!.nome,
    categoria_beneficiario: "padrao",
    vigencia_inicio: inicio,
    vigencia_fim: fim,
    valor: quanto,
    origem,
    criado_por_nome: origem === "fgd" ? "Fátima FGD" : null,
    criado_em: "2026-01-01T00:00:00Z",
  };
}

const VALORES = [
  valor(10, 1, "2025-01-01", "2025-12-31", "425.00", "federal"),
  valor(11, 1, "2026-01-01", null, "480.00", "fgd"),
  valor(20, 2, "2025-01-01", null, "300.00", "federal"),
  valor(21, 2, "2099-01-01", null, "350.00", "fgd"),
];

const PARAMETROS: ParametrosDiarias = {
  regra_inteira_por_pernoite: true,
  regra_meia_no_retorno: true,
  regra_meia_sem_pernoite: true,
  regra_meia_hospedagem_custeada: true,
  adicional_embarque_ativo: false,
  adicional_embarque_valor: "95.00",
};

function montar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TabelaDiariasPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mocks.perfis = ["fgd"];
  for (const m of Object.values(mocks)) if (typeof m === "function") m.mockReset();
  mocks.listarFaixas.mockResolvedValue(FAIXAS);
  mocks.listarValores.mockResolvedValue(VALORES);
  mocks.lerParametros.mockResolvedValue(PARAMETROS);
});

describe("Tabela de diárias (#366)", () => {
  it("quem não é Super Admin nem FGD não vê a tela nem consulta a tabela", () => {
    mocks.perfis = ["ugp"];
    montar();

    expect(screen.queryByTestId("grade-diarias")).toBeNull();
    expect(mocks.listarFaixas).not.toHaveBeenCalled();
  });

  it("a grade cruza faixa e vigência e mostra a origem de cada valor", async () => {
    montar();
    const grade = await screen.findByTestId("grade-diarias");

    const colunas = within(grade).getAllByRole("columnheader").map((th) => th.textContent);
    expect(colunas.slice(0, 4)).toEqual([
      "Faixa de destino",
      "A partir de 01/01/2099",
      "A partir de 01/01/2026",
      "A partir de 01/01/2025",
    ]);

    // Faixa 1: o valor da FGD em 2026 e o federal em 2025.
    expect(screen.getByTestId("grade-celula-1-1").textContent).toContain("480,00");
    expect(screen.getByTestId("grade-celula-1-1").textContent).toContain("Valor FGD");
    expect(screen.getByTestId("grade-celula-1-2").textContent).toContain("425,00");
    expect(screen.getByTestId("grade-celula-1-2").textContent).toContain("Federal");
    // Faixa 2 não mudou em 2026: segue com o valor de 2025.
    expect(screen.getByTestId("grade-celula-2-1").textContent).toContain("300,00");
    expect(screen.getByTestId("grade-celula-2-1").textContent).toContain("desde 01/01/2025");
    // Faixa sem valor nenhum.
    expect(screen.getByTestId("grade-editar-3").textContent).toBe("Cadastrar valor");
  });

  it("o histórico lista as vigências da faixa e só deixa excluir a que ainda não vigorou", async () => {
    mocks.excluirValor.mockResolvedValue(undefined);
    montar();
    fireEvent.click(await screen.findByTestId("grade-historico-2"));

    const historico = screen.getByTestId("historico-faixa-2");
    expect(within(historico).getByTestId("historico-valor-20").textContent).toContain("01/01/2025 a em aberto");
    expect(within(historico).getByTestId("historico-valor-20").textContent).toContain("Vigente");
    expect(within(historico).getByTestId("historico-valor-21").textContent).toContain("Ainda não vigora");
    expect(within(historico).getByTestId("historico-valor-21").textContent).toContain("Fátima FGD");
    expect(screen.queryByTestId("historico-excluir-20")).toBeNull();

    fireEvent.click(screen.getByTestId("historico-excluir-21"));
    expect((await screen.findByTestId("confirm-delete-dialog")).textContent).toContain("350,00");
    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));
    await waitFor(() => expect(mocks.excluirValor).toHaveBeenCalledWith(21));
  });

  it("editar um valor pede a data de início da nova vigência", async () => {
    mocks.registrarNovaVigencia.mockResolvedValue(valor(12, 1, "2027-01-01", null, "500.00", "fgd"));
    montar();
    fireEvent.click(await screen.findByTestId("grade-editar-1"));

    const form = await screen.findByTestId("valor-diaria-form");
    expect(screen.getByTestId("valor-diaria-atual").textContent).toContain("480,00");

    fireEvent.change(within(form).getByLabelText(/Novo valor da diária/), { target: { value: "50000" } });
    fireEvent.click(screen.getByTestId("valor-diaria-salvar"));
    expect(within(form).getByText("Informe a data de início da vigência.")).toBeTruthy();
    expect(mocks.registrarNovaVigencia).not.toHaveBeenCalled();

    // Não pode começar junto com a vigência que está sendo encerrada.
    fireEvent.change(within(form).getByLabelText(/Início da nova vigência/), { target: { value: "2026-01-01" } });
    fireEvent.click(screen.getByTestId("valor-diaria-salvar"));
    expect(mocks.registrarNovaVigencia).not.toHaveBeenCalled();

    fireEvent.change(within(form).getByLabelText(/Início da nova vigência/), { target: { value: "2027-01-01" } });
    fireEvent.click(screen.getByTestId("valor-diaria-salvar"));

    await waitFor(() =>
      expect(mocks.registrarNovaVigencia).toHaveBeenCalledWith(11, {
        valor: "500.00",
        vigencia_inicio: "2027-01-01",
        origem: "fgd",
      }),
    );
    expect(mocks.criarValor).not.toHaveBeenCalled();
  });

  it("a faixa sem valor cadastra o primeiro, e a sobreposição do backend aparece na data", async () => {
    mocks.criarValor.mockRejectedValue(
      new ApiError(400, {
        code: "validation_error",
        message: "Dados inválidos.",
        field_errors: [{ field: "vigencia_inicio", message: "A vigência se sobrepõe à de 01/01/2026 a em aberto." }],
      }),
    );
    montar();
    fireEvent.click(await screen.findByTestId("grade-editar-3"));

    const form = await screen.findByTestId("valor-diaria-form");
    fireEvent.change(within(form).getByLabelText(/Novo valor da diária/), { target: { value: "90000" } });
    fireEvent.change(within(form).getByLabelText(/Início da nova vigência/), { target: { value: "2026-03-01" } });
    fireEvent.change(screen.getByTestId("valor-diaria-origem"), { target: { value: "federal" } });
    fireEvent.click(screen.getByTestId("valor-diaria-salvar"));

    await waitFor(() =>
      expect(mocks.criarValor).toHaveBeenCalledWith(3, {
        valor: "900.00",
        vigencia_inicio: "2026-03-01",
        origem: "federal",
      }),
    );
    expect(await within(form).findByText(/A vigência se sobrepõe/)).toBeTruthy();
  });

  it("a lista de municípios da faixa é editável e vai inteira ao salvar", async () => {
    mocks.salvarEnquadramentos.mockResolvedValue({ ...FAIXAS[0], enquadramentos: [NATAL] });
    montar();
    const bloco = await screen.findByTestId("faixa-municipios-1");
    expect(within(bloco).getByTestId("faixa-1-municipio-5300108").textContent).toContain("Brasília");
    expect(screen.queryByTestId("faixa-1-salvar")).toBeNull();

    fireEvent.click(within(bloco).getByTestId("faixa-1-adicionar"));
    fireEvent.click(within(bloco).getByRole("button", { name: /Remover Brasília/ }));
    fireEvent.click(screen.getByTestId("faixa-1-salvar"));

    await waitFor(() => expect(mocks.salvarEnquadramentos).toHaveBeenCalledWith(1, [NATAL]));
  });

  it("município que já está em outra faixa mostra a recusa do backend", async () => {
    mocks.salvarEnquadramentos.mockRejectedValue(
      new ApiError(400, {
        code: "validation_error",
        message: "Dados inválidos.",
        field_errors: [
          { field: "enquadramentos", message: "Município já enquadrado em outra faixa: 2408102 (Demais capitais)." },
        ],
      }),
    );
    montar();
    const bloco = await screen.findByTestId("faixa-municipios-1");
    fireEvent.click(within(bloco).getByTestId("faixa-1-adicionar"));
    fireEvent.click(screen.getByTestId("faixa-1-salvar"));

    expect((await screen.findByTestId("faixa-1-erro")).textContent).toContain("já enquadrado em outra faixa");
  });

  it("os parâmetros de contagem são salvos juntos, só quando mudam", async () => {
    mocks.salvarParametros.mockResolvedValue({ ...PARAMETROS, regra_meia_no_retorno: false });
    montar();
    const bloco = await screen.findByTestId("parametros-diarias");
    const salvar = screen.getByTestId("parametros-diarias-salvar") as HTMLButtonElement;
    expect(salvar.disabled).toBe(true);
    expect((within(bloco).getByLabelText(/Valor do adicional/) as HTMLInputElement).value).toContain("95,00");

    fireEvent.click(screen.getByTestId("parametro-regra_meia_no_retorno"));
    fireEvent.click(screen.getByTestId("parametro-adicional_embarque_ativo"));
    expect(salvar.disabled).toBe(false);
    fireEvent.click(salvar);

    await waitFor(() =>
      expect(mocks.salvarParametros).toHaveBeenCalledWith({
        ...PARAMETROS,
        regra_meia_no_retorno: false,
        adicional_embarque_ativo: true,
        adicional_embarque_valor: "95.00",
      }),
    );
  });

  it("não liga o adicional de embarque sem valor", async () => {
    mocks.lerParametros.mockResolvedValue({ ...PARAMETROS, adicional_embarque_valor: "0.00" });
    montar();
    await screen.findByTestId("parametros-diarias");

    fireEvent.click(screen.getByTestId("parametro-adicional_embarque_ativo"));

    expect(screen.getByText("Informe o valor do adicional para ligá-lo.")).toBeTruthy();
    expect((screen.getByTestId("parametros-diarias-salvar") as HTMLButtonElement).disabled).toBe(true);
  });
});
