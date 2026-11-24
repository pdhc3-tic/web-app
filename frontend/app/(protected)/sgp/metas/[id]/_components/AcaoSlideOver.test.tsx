import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Acao } from "@/app/lib/acoes";
import type { Rubrica } from "@/app/lib/tiposSolicitacao";
import { AcaoSlideOver } from "./AcaoSlideOver";

/** #452 — número sugerido, rubricas previstas e obrigatórios da Nova Ação. */

// A função do mock é trocada a cada teste: um `vi.fn` criado no `vi.hoisted`
// que rejeita reprova o teste mesmo com o erro tratado (Vitest 4).
const api = vi.hoisted(() => ({
  criar: (() => Promise.resolve()) as (payload: unknown) => Promise<unknown>,
  atualizar: (() => Promise.resolve()) as (id: number, payload: unknown) => Promise<unknown>,
}));
vi.mock("@/app/lib/acoes", async (original) => ({
  ...(await original<typeof import("@/app/lib/acoes")>()),
  listSubmetasDaMeta: async () => [
    { id: 11, numero: "1.1", titulo: "Assistência técnica" },
    { id: 12, numero: "1.2", titulo: "Crédito" },
  ],
  listIndicadores: async () => [{ id: 7, codigo: "IND-FAM", nome: "Famílias atendidas" }],
  createAcao: (payload: unknown) => api.criar(payload),
  updateAcao: (id: number, payload: unknown) => api.atualizar(id, payload),
}));

const EXISTENTES = [
  { id: 1, numero: "1.1.1" },
  { id: 2, numero: "1.1.2" },
  { id: 3, numero: "1.2.1" },
];

const RUBRICAS: Rubrica[] = [
  { id: 21, slug: "diarias", nome: "Diárias", ativo: true },
  { id: 22, slug: "material", nome: "Material de consumo", ativo: true },
  { id: 23, slug: "antiga", nome: "Rubrica antiga", ativo: false },
];

const ACAO = {
  id: 2,
  submeta: 11,
  submeta_numero: "1.1",
  indicador: 7,
  numero: "1.1.2",
  descricao: "Visitas técnicas",
  quantidade_planejada: "12.00",
  valor_unitario: "350.00",
  data_inicio: "2026-03-01",
  data_fim: "2026-12-31",
  rubricas_previstas: [23],
} as unknown as Acao;

let criar = vi.fn();
let atualizar = vi.fn();
beforeEach(() => {
  criar = vi.fn();
  atualizar = vi.fn();
  api.criar = (payload) => criar(payload);
  api.atualizar = (id, payload) => atualizar(id, payload);
});

function montar(props: Partial<Parameters<typeof AcaoSlideOver>[0]> = {}) {
  const onSaved = vi.fn();
  render(
    <AcaoSlideOver
      open
      onClose={vi.fn()}
      mode="create"
      metaId={1}
      existentes={EXISTENTES}
      rubricas={RUBRICAS}
      onSaved={onSaved}
      {...props}
    />,
  );
  return onSaved;
}

function numero(): HTMLInputElement {
  return screen.getByTestId("acao-form-numero") as HTMLInputElement;
}

async function escolher(testId: string, opcao: RegExp) {
  fireEvent.click(within(await screen.findByTestId(testId)).getByRole("combobox"));
  // O Select escolhe no mousedown (antes do blur fechar a lista).
  fireEvent.mouseDown(await screen.findByRole("option", { name: opcao }));
}

async function preencherObrigatorios() {
  await escolher("acao-form-indicador", /^IND-FAM/);
  fireEvent.change(screen.getByTestId("acao-form-descricao"), { target: { value: "Oficinas de manejo" } });
  fireEvent.change(screen.getByLabelText(/Quantidade planejada/), { target: { value: "4" } });
  fireEvent.change(screen.getByLabelText(/Valor unitário/), { target: { value: "150000" } });
  fireEvent.change(screen.getByLabelText(/Data de início/), { target: { value: "2026-03-01" } });
  fireEvent.change(screen.getByLabelText(/Data de término/), { target: { value: "2026-12-31" } });
}

describe("AcaoSlideOver (#452)", () => {
  it("abre sem número e sugere o próximo livre ao escolher a Submeta", async () => {
    montar();
    await screen.findByTestId("acao-form");
    expect(numero().value).toBe("");

    await escolher("acao-form-submeta", /^1\.1 —/);
    expect(numero().value).toBe("1.1.3");

    // Trocar de Submeta troca a sugestão.
    await escolher("acao-form-submeta", /^1\.2 —/);
    expect(numero().value).toBe("1.2.2");
  });

  it("não sobrescreve o número digitado à mão", async () => {
    montar();
    await screen.findByTestId("acao-form");
    fireEvent.change(numero(), { target: { value: "1.2.9" } });
    await escolher("acao-form-submeta", /^1\.2 —/);
    expect(numero().value).toBe("1.2.9");
  });

  it("envia as rubricas marcadas junto com a Ação", async () => {
    const criada = { id: 99 };
    criar.mockResolvedValue(criada);
    const onSaved = montar();
    await escolher("acao-form-submeta", /^1\.1 —/);
    await preencherObrigatorios();
    // A inativa não é oferecida numa Ação nova.
    expect(screen.queryByText(/Rubrica antiga/)).toBeNull();
    fireEvent.click(screen.getByTestId("acao-form-rubrica-22"));
    fireEvent.click(screen.getByTestId("acao-form-rubrica-21"));
    fireEvent.click(screen.getByTestId("acao-form-submit"));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(criada, "create"));
    expect(criar).toHaveBeenCalledWith(
      expect.objectContaining({
        submeta: 11,
        numero: "1.1.3",
        quantidade_planejada: "4",
        valor_unitario: "1500.00",
        rubricas_previstas: [22, 21],
      }),
    );
  });

  it("quantidade, valor unitário e datas são obrigatórios", async () => {
    montar();
    await escolher("acao-form-submeta", /^1\.1 —/);
    fireEvent.click(screen.getByTestId("acao-form-submit"));

    expect(await screen.findByText("Informe a quantidade planejada.")).toBeInTheDocument();
    expect(screen.getByText("Informe o valor unitário.")).toBeInTheDocument();
    expect(screen.getByText("Informe a data de início.")).toBeInTheDocument();
    expect(screen.getByText("Informe a data de término.")).toBeInTheDocument();
    expect(criar).not.toHaveBeenCalled();
  });

  it("quantidade zero não é aceita", async () => {
    montar();
    await escolher("acao-form-submeta", /^1\.1 —/);
    await preencherObrigatorios();
    fireEvent.change(screen.getByLabelText(/Quantidade planejada/), { target: { value: "0" } });
    fireEvent.click(screen.getByTestId("acao-form-submit"));

    expect(await screen.findByText("A quantidade planejada precisa ser maior que zero.")).toBeInTheDocument();
    expect(criar).not.toHaveBeenCalled();
  });

  it("número fora da Submeta escolhida é recusado antes do envio", async () => {
    montar();
    await escolher("acao-form-submeta", /^1\.1 —/);
    await preencherObrigatorios();
    fireEvent.change(numero(), { target: { value: "1.2.5" } });
    fireEvent.click(screen.getByTestId("acao-form-submit"));

    expect(await screen.findByText("O número da Ação deve começar com 1.1. (número da Submeta).")).toBeInTheDocument();
    expect(criar).not.toHaveBeenCalled();
  });

  it("na edição, mantém a rubrica inativa já gravada e o número ao voltar à Submeta original", async () => {
    atualizar.mockResolvedValue(ACAO);
    const onSaved = montar({ mode: "edit", acao: ACAO });
    await screen.findByTestId("acao-form");
    await waitFor(() => expect(numero().value).toBe("1.1.2"));

    const inativa = screen.getByTestId("acao-form-rubrica-23") as HTMLInputElement;
    expect(inativa.checked).toBe(true);
    expect(screen.getByText("Rubrica antiga (inativa)")).toBeInTheDocument();

    // Mudar de Submeta sugere o número nela; voltar devolve o da Ação.
    await escolher("acao-form-submeta", /^1\.2 —/);
    expect(numero().value).toBe("1.2.2");
    await escolher("acao-form-submeta", /^1\.1 —/);
    expect(numero().value).toBe("1.1.2");

    fireEvent.click(screen.getByTestId("acao-form-submit"));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(atualizar).toHaveBeenCalledWith(2, expect.objectContaining({ numero: "1.1.2", rubricas_previstas: [23] }));
  });
});
