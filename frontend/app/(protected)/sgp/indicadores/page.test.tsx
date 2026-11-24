import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import type { Indicador } from "@/app/lib/indicadores";
import IndicadoresPage from "./page";

/** #453 — Catálogo de Indicadores. */

const mocks = vi.hoisted(() => ({
  canManage: true,
  showToast: vi.fn(),
  listar: vi.fn(),
  criar: vi.fn(),
  atualizar: vi.fn(),
  excluir: vi.fn(),
}));

vi.mock("@/app/lib/auth/roles", async (original) => ({
  ...(await original<typeof import("@/app/lib/auth/roles")>()),
  useCanManageWorkPlan: () => ({ loading: false, canManage: mocks.canManage }),
}));
vi.mock("@/app/components/layout/PageHeader", () => ({
  PageHeader: ({ children }: { children: React.ReactNode }) => <header>{children}</header>,
}));
vi.mock("@/app/components/ui/Toast/Toast", () => ({ useToast: () => ({ showToast: mocks.showToast }) }));
vi.mock("@/app/lib/hooks/useDebounced", () => ({ useDebounced: <T,>(v: T) => v }));
vi.mock("@/app/providers/SgpChoicesProvider", () => ({
  useSgpChoices: () => ({ ods: [{ value: "1", label: "ODS 1 - Erradicação da pobreza" }, { value: "2", label: "ODS 2 - Fome zero" }] }),
}));
// O Select do design system abre uma lista própria; no teste, um <select> nativo.
vi.mock("@/app/components/ui/Select/Select", () => ({
  Select: ({
    id,
    label,
    options,
    value,
    onChange,
    error,
  }: {
    id: string;
    label: string;
    options: { value: string; label: string }[];
    value: string;
    onChange: (v: string) => void;
    error?: string;
  }) => (
    <label>
      {label}
      <select data-testid={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">—</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && <span>{error}</span>}
    </label>
  ),
}));
vi.mock("@/app/lib/indicadores", async (original) => ({
  ...(await original<typeof import("@/app/lib/indicadores")>()),
  listarIndicadores: mocks.listar,
  criarIndicador: mocks.criar,
  atualizarIndicador: mocks.atualizar,
  excluirIndicador: mocks.excluir,
}));

function indicador(id: number, extra: Partial<Indicador> = {}): Indicador {
  return {
    id,
    codigo: `IND-${id}`,
    nome: `Indicador ${id}`,
    unidade_medida: "familia",
    forma_apuracao: "soma_ufpas",
    categoria: "formacao",
    ods_ids: [1, 2],
    desagregacoes: ["genero", "territorio"],
    ativo: true,
    criado_por: null,
    criado_em: "2026-01-01T00:00:00Z",
    atualizado_em: "2026-01-01T00:00:00Z",
    ...extra,
  } as Indicador;
}

const pagina = (itens: Indicador[]) => ({ count: itens.length, next: null, previous: null, results: itens });

function montar() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <IndicadoresPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mocks.canManage = true;
  for (const m of [mocks.showToast, mocks.listar, mocks.criar, mocks.atualizar, mocks.excluir]) m.mockReset();
  mocks.listar.mockResolvedValue(pagina([indicador(1), indicador(2, { ativo: false, categoria: "" })]));
});

describe("Catálogo de Indicadores (#453)", () => {
  it("lista os indicadores com rótulos e pede só os ativos por padrão", async () => {
    montar();
    const linha = await screen.findByTestId("indicador-linha-1");

    expect(linha).toHaveTextContent("IND-1");
    expect(linha).toHaveTextContent("Família");
    expect(linha).toHaveTextContent("Soma de UFPAs vinculadas");
    expect(linha).toHaveTextContent("Formação");
    expect(linha).toHaveTextContent("Gênero, Território");
    expect(mocks.listar).toHaveBeenCalledWith(
      expect.objectContaining({ situacao: "ativos" }),
      { offset: 0, limit: 25 },
      expect.anything(),
    );
  });

  it("os filtros vão para a consulta", async () => {
    montar();
    await screen.findByTestId("indicador-linha-1");

    fireEvent.change(screen.getByTestId("indicadores-situacao"), { target: { value: "todos" } });
    fireEvent.change(screen.getByTestId("indicadores-forma"), { target: { value: "manual" } });

    await waitFor(() =>
      expect(mocks.listar).toHaveBeenLastCalledWith(
        expect.objectContaining({ situacao: "todos", forma_apuracao: "manual" }),
        expect.anything(),
        expect.anything(),
      ),
    );
  });

  it("mudar filtro na página 2 consulta já a primeira página (revisão)", async () => {
    mocks.listar.mockResolvedValue({ count: 60, next: "x", previous: null, results: [indicador(1)] });
    montar();
    await screen.findByTestId("indicador-linha-1");

    fireEvent.click(screen.getByRole("button", { name: "Próxima página" }));
    await waitFor(() =>
      expect(mocks.listar).toHaveBeenLastCalledWith(expect.anything(), { offset: 25, limit: 25 }, expect.anything()),
    );

    fireEvent.change(screen.getByTestId("indicadores-situacao"), { target: { value: "inativos" } });
    await waitFor(() =>
      expect(mocks.listar).toHaveBeenLastCalledWith(
        expect.objectContaining({ situacao: "inativos" }),
        { offset: 0, limit: 25 },
        expect.anything(),
      ),
    );
    // Nenhuma consulta com o filtro novo e a página antiga: o backend responderia 404.
    const comPaginaAntiga = mocks.listar.mock.calls.filter(
      ([f, p]) => (f as { situacao: string }).situacao === "inativos" && (p as { offset: number }).offset !== 0,
    );
    expect(comPaginaAntiga).toEqual([]);
  });

  it("quem só lê não vê botões de escrita", async () => {
    mocks.canManage = false;
    montar();
    await screen.findByTestId("indicador-linha-1");

    expect(screen.queryByTestId("indicador-novo-btn")).toBeNull();
    expect(screen.queryByTestId("indicador-editar-1")).toBeNull();
    expect(screen.queryByTestId("indicador-excluir-1")).toBeNull();
  });

  it("cadastra um indicador com os campos da DRS", async () => {
    mocks.criar.mockResolvedValue(indicador(9, { codigo: "IND-NOVO" }));
    montar();
    await screen.findByTestId("indicador-linha-1");

    fireEvent.click(screen.getByTestId("indicador-novo-btn"));
    const form = await screen.findByTestId("indicador-form");
    fireEvent.change(within(form).getByTestId("indicador-form-codigo"), { target: { value: " IND-NOVO " } });
    fireEvent.change(within(form).getByTestId("indicador-form-nome"), { target: { value: "Famílias formadas" } });
    fireEvent.change(within(form).getByTestId("indicador-form-unidade"), { target: { value: "familia" } });
    fireEvent.change(within(form).getByTestId("indicador-form-forma"), { target: { value: "manual" } });
    fireEvent.click(within(form).getByLabelText("Gênero"));
    fireEvent.click(screen.getByTestId("indicador-form-salvar"));

    await waitFor(() =>
      expect(mocks.criar).toHaveBeenCalledWith({
        codigo: "IND-NOVO",
        nome: "Famílias formadas",
        unidade_medida: "familia",
        forma_apuracao: "manual",
        categoria: "",
        ods_ids: [],
        desagregacoes: ["genero"],
        ativo: true,
      }),
    );
    expect(mocks.showToast).toHaveBeenCalledWith("Indicador IND-NOVO cadastrado.", "success");
  });

  it("sem os obrigatórios, não envia", async () => {
    montar();
    await screen.findByTestId("indicador-linha-1");
    fireEvent.click(screen.getByTestId("indicador-novo-btn"));
    fireEvent.click(await screen.findByTestId("indicador-form-salvar"));

    expect(await screen.findByText("Informe o código do indicador.")).toBeInTheDocument();
    expect(mocks.criar).not.toHaveBeenCalled();
  });

  it("o erro de campo do servidor aparece no campo", async () => {
    mocks.criar.mockRejectedValue(
      new ApiError(400, {
        code: "validation_error",
        message: "Dados inválidos.",
        field_errors: [{ field: "codigo", message: "indicator com este Código já existe." }],
      }),
    );
    montar();
    await screen.findByTestId("indicador-linha-1");
    fireEvent.click(screen.getByTestId("indicador-novo-btn"));
    const form = await screen.findByTestId("indicador-form");
    fireEvent.change(within(form).getByTestId("indicador-form-codigo"), { target: { value: "IND-1" } });
    fireEvent.change(within(form).getByTestId("indicador-form-nome"), { target: { value: "Repetido" } });
    fireEvent.change(within(form).getByTestId("indicador-form-unidade"), { target: { value: "familia" } });
    fireEvent.change(within(form).getByTestId("indicador-form-forma"), { target: { value: "manual" } });
    fireEvent.click(screen.getByTestId("indicador-form-salvar"));

    expect(await within(form).findByText("indicator com este Código já existe.")).toBeInTheDocument();
  });

  it("trocar a forma de um indicador em uso pede confirmação e reenvia com o sinal", async () => {
    const mensagem =
      "Trocar a forma de apuração recalcula a quantidade realizada de 3 Ação(ões). Reenvie com confirmar_recalculo=true para confirmar.";
    mocks.atualizar
      .mockRejectedValueOnce(new ApiError(409, { code: "confirmacao_necessaria", message: mensagem }))
      .mockResolvedValueOnce(indicador(1, { forma_apuracao: "manual" }));
    montar();
    await screen.findByTestId("indicador-linha-1");

    fireEvent.click(screen.getByTestId("indicador-editar-1"));
    const form = await screen.findByTestId("indicador-form");
    fireEvent.change(within(form).getByTestId("indicador-form-forma"), { target: { value: "manual" } });
    fireEvent.click(screen.getByTestId("indicador-form-salvar"));

    const aviso = await screen.findByTestId("indicador-recalculo");
    expect(aviso).toHaveTextContent("3 Ação(ões)");
    expect(aviso).not.toHaveTextContent("confirmar_recalculo");
    expect(mocks.atualizar).toHaveBeenLastCalledWith(1, expect.objectContaining({ forma_apuracao: "manual" }), false);

    fireEvent.click(screen.getByTestId("indicador-confirmar-recalculo"));
    await waitFor(() =>
      expect(mocks.atualizar).toHaveBeenLastCalledWith(1, expect.objectContaining({ forma_apuracao: "manual" }), true),
    );
    expect(mocks.showToast).toHaveBeenCalledWith("Indicador IND-1 atualizado.", "success");
  });

  it("excluir um indicador em uso oferece inativar", async () => {
    mocks.excluir.mockRejectedValue(
      new ApiError(409, {
        code: "indicador_em_uso",
        message: "Indicador vinculado a Ações não pode ser excluído; inative-o.",
      }),
    );
    mocks.atualizar.mockResolvedValue(indicador(1, { ativo: false }));
    montar();
    await screen.findByTestId("indicador-linha-1");

    fireEvent.click(screen.getByTestId("indicador-excluir-1"));
    fireEvent.click(await screen.findByTestId("indicador-excluir-confirmar"));

    await waitFor(() => expect(screen.getByTestId("indicador-excluir-confirmar")).toHaveTextContent("Inativar"));
    expect(screen.getByTestId("indicador-exclusao")).toHaveTextContent("não pode ser excluído");

    fireEvent.click(screen.getByTestId("indicador-excluir-confirmar"));
    await waitFor(() => expect(mocks.atualizar).toHaveBeenCalledWith(1, { ativo: false }));
    expect(mocks.showToast).toHaveBeenCalledWith("Indicador IND-1 inativado.", "success");
  });

  it("sem uso, exclui", async () => {
    mocks.excluir.mockResolvedValue(undefined);
    montar();
    await screen.findByTestId("indicador-linha-2");

    fireEvent.click(screen.getByTestId("indicador-excluir-2"));
    fireEvent.click(await screen.findByTestId("indicador-excluir-confirmar"));

    await waitFor(() => expect(mocks.excluir).toHaveBeenCalledWith(2));
    expect(mocks.showToast).toHaveBeenCalledWith("Indicador IND-2 excluído.", "success");
  });
});
