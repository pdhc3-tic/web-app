import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/app/lib/api";
import { SubmetaSlideOver } from "./SubmetaSlideOver";

/** #431 — cadastro de Submeta no detalhe da Meta. */

// A função do mock é trocada a cada teste: um `vi.fn` criado no `vi.hoisted`
// que rejeita reprova o teste mesmo com o erro tratado (Vitest 4).
const api = vi.hoisted(() => ({ criar: (() => Promise.resolve()) as (payload: unknown) => Promise<unknown> }));
vi.mock("@/app/lib/submetas", async (original) => ({
  ...(await original<typeof import("@/app/lib/submetas")>()),
  criarSubmeta: (payload: unknown) => api.criar(payload),
}));

const META = { id: 9, numero: 3, data_inicio: "2026-01-01", data_fim: "2027-12-31" };

function montar(existentes = [{ numero: "3.1" }]) {
  const onSaved = vi.fn();
  render(<SubmetaSlideOver open onClose={vi.fn()} meta={META} existentes={existentes} onSaved={onSaved} />);
  return onSaved;
}

let criar = vi.fn();
beforeEach(() => {
  criar = vi.fn();
  api.criar = (payload) => criar(payload);
});

describe("SubmetaSlideOver (#431)", () => {
  it("abre com o próximo número livre e o período da Meta", async () => {
    montar();
    // O SlideOver monta no quadro seguinte (requestAnimationFrame).
    const numero = (await screen.findByTestId("submeta-form-numero")).querySelector("input") ?? screen.getByTestId("submeta-form-numero");
    expect((numero as HTMLInputElement).value).toBe("3.2");
    expect(screen.getByLabelText(/Data de início/)).toHaveValue("2026-01-01");
    expect(screen.getByLabelText(/Data de término/)).toHaveValue("2027-12-31");
  });

  it("sem título não envia", async () => {
    montar();
    fireEvent.click(await screen.findByTestId("submeta-form-submit"));
    expect(await screen.findByText("Informe o título da Submeta.")).toBeInTheDocument();
    expect(criar).not.toHaveBeenCalled();
  });

  it("envia o payload e devolve a Submeta criada", async () => {
    const criada = { id: 41, numero: "3.2", titulo: "Assistência técnica" };
    criar.mockResolvedValue(criada);
    const onSaved = montar();
    fireEvent.change(await screen.findByLabelText(/Título/), { target: { value: "Assistência técnica" } });
    fireEvent.click(screen.getByTestId("submeta-form-submit"));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(criada));
    expect(criar).toHaveBeenCalledWith({
      meta: 9,
      numero: "3.2",
      titulo: "Assistência técnica",
      descricao: "",
      data_inicio: "2026-01-01",
      data_fim: "2027-12-31",
    });
  });

  it("mostra no campo o erro do backend", async () => {
    const msg = "Já existe uma Submeta com este número nesta Meta.";
    const recusa = new ApiError(400, {
      code: "validation_error",
      message: msg,
      field_errors: [{ field: "numero", message: msg }],
    });
    criar.mockRejectedValue(recusa);
    const onSaved = montar();
    fireEvent.change(await screen.findByLabelText(/Título/), { target: { value: "Duplicada" } });
    fireEvent.click(screen.getByTestId("submeta-form-submit"));

    await waitFor(() => expect(criar).toHaveBeenCalled());
    expect(await screen.findAllByText(msg)).not.toHaveLength(0);
    expect(onSaved).not.toHaveBeenCalled();
  });
});
