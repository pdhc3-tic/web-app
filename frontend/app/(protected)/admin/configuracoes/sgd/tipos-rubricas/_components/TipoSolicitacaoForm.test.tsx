import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { TipoSolicitacaoForm } from "./TipoSolicitacaoForm";

/** #365 — o cadastro de um tipo do catálogo: editor do schema, pré-visualização e envio. */

vi.mock("@/app/lib/tiposSolicitacao", async (original) => ({
  ...(await original<typeof import("@/app/lib/tiposSolicitacao")>()),
  listRubricas: async () => [{ id: 1, slug: "diarias", nome: "Diárias", ativo: true }],
}));

vi.mock("@/app/providers/SgpChoicesProvider", () => ({ useSgpChoices: () => ({}) }));

vi.mock("@/app/components/ui/Select/Select", () => ({
  Select: ({
    id,
    options,
    value,
    onChange,
    error,
  }: {
    id: string;
    options: { value: string; label: string }[];
    value: string;
    onChange: (v: string) => void;
    error?: string;
  }) => (
    <div>
      <select data-testid={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="" />
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && <p>{error}</p>}
    </div>
  ),
}));

async function abrir(onSalvar = vi.fn(async () => {})) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TipoSolicitacaoForm editando={null} onClose={vi.fn()} onSalvar={onSalvar} />
    </QueryClientProvider>,
  );
  // O SlideOver monta o conteúdo num efeito, depois do primeiro render.
  await screen.findByTestId("tipo-form");
  return onSalvar;
}

const schemaEditor = () => screen.getByLabelText(/Campos do formulário/) as HTMLTextAreaElement;

describe("TipoSolicitacaoForm (#365)", () => {
  it("o nome sugere o identificador, e a pré-visualização desenha o schema inicial", async () => {
    await abrir();
    fireEvent.change(screen.getByLabelText(/^Nome/), { target: { value: "Hospedagem em Pousada" } });
    expect((screen.getByLabelText(/^Identificador/) as HTMLInputElement).value).toBe("hospedagem-em-pousada");
    expect(screen.getByTestId("tipo-previa").textContent).toContain("Descrição");
  });

  it("a pré-visualização acompanha o schema e mostra o erro de JSON na hora", async () => {
    await abrir();
    fireEvent.change(schemaEditor(), {
      target: {
        value: JSON.stringify({
          required: ["hotel"],
          properties: {
            hotel: { type: "string", title: "Hotel", "x-ordem": 1 },
            cafe: { type: "boolean", title: "Café incluso?", "x-ordem": 2 },
          },
        }),
      },
    });
    const previa = screen.getByTestId("tipo-previa");
    expect(previa.textContent).toContain("Hotel");
    expect(previa.textContent).toContain("Café incluso?");

    fireEvent.change(schemaEditor(), { target: { value: "{ quebrado" } });
    expect(screen.getByText(/JSON inválido/)).toBeTruthy();
    expect(screen.queryByTestId("tipo-previa")).toBeNull();
  });

  it("não envia sem os obrigatórios nem com JSON quebrado", async () => {
    const onSalvar = await abrir();
    fireEvent.change(schemaEditor(), { target: { value: "[]" } });
    fireEvent.click(screen.getByTestId("tipo-salvar"));
    expect(await screen.findByText("Informe o nome.")).toBeTruthy();
    expect(screen.getAllByText("O schema precisa ser um objeto JSON.").length).toBeGreaterThan(0);
    expect(onSalvar).not.toHaveBeenCalled();
  });

  it("envia o tipo com o schema lido do editor", async () => {
    const onSalvar = await abrir();
    fireEvent.change(screen.getByLabelText(/^Nome/), { target: { value: "Hospedagem" } });
    await waitFor(() => expect(screen.getByTestId("tipo-rubrica").querySelectorAll("option").length).toBe(2));
    fireEvent.change(screen.getByTestId("tipo-rubrica"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/^Ordem/), { target: { value: "7" } });
    fireEvent.click(screen.getByTestId("tipo-salvar"));

    await waitFor(() => expect(onSalvar).toHaveBeenCalledTimes(1));
    expect(onSalvar).toHaveBeenCalledWith({
      slug: "hospedagem",
      nome: "Hospedagem",
      rubrica: 1,
      ordem: 7,
      ativo: true,
      schema_campos: {
        type: "object",
        required: ["descricao"],
        properties: { descricao: { type: "string", title: "Descrição", "x-ordem": 1 } },
      },
    });
  });
});
