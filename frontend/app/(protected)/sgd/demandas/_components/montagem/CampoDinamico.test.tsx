import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  configDoSchema,
  montarCamposJson,
  validarCampos,
  type ConfigTipo,
  type ValoresCampos,
} from "@/app/lib/camposSolicitacao";
import type { SchemaCampos } from "@/app/lib/tiposSolicitacao";
import { CampoDinamico } from "./CampoDinamico";

/**
 * #365 — o renderizador genérico, campo a campo: cada tipo que o `schema_campos`
 * declara vira o controle certo, aceita a digitação do usuário e chega ao
 * `campos_json` com o tipo do JSON Schema. O anexo entra quando o backend
 * definir o contrato (pendencias-backend-sprint-12a.md, item 1).
 */

vi.mock("@/app/providers/SgpChoicesProvider", () => ({ useSgpChoices: () => ({}) }));

// O Select do design system é um listbox; aqui basta um <select> com o mesmo contrato.
vi.mock("@/app/components/ui/Select/Select", () => ({
  Select: ({
    id,
    label,
    options,
    value,
    onChange,
    helperText,
    error,
  }: {
    id: string;
    label: string;
    options: { value: string; label: string }[];
    value: string;
    onChange: (v: string) => void;
    helperText?: string;
    error?: string;
  }) => (
    <div>
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="" />
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {helperText && <p>{helperText}</p>}
      {error && <p>{error}</p>}
    </div>
  ),
}));

const SCHEMA: SchemaCampos = {
  type: "object",
  required: ["hotel", "diarias"],
  properties: {
    hotel: { type: "string", title: "Hotel", description: "Nome do estabelecimento", "x-ordem": 1 },
    observacoes: { type: "string", title: "Observações", maxLength: 500, "x-ordem": 2 },
    diarias: { type: "integer", title: "Diárias", minimum: 1, "x-ordem": 3 },
    valor_diaria: { type: "number", title: "Valor da diária", "x-ordem": 4 },
    check_in: { type: "string", format: "date", title: "Check-in", "x-ordem": 5 },
    chegada: { type: "string", format: "date-time", title: "Chegada", "x-ordem": 6 },
    categoria: { enum: ["simples", "luxo"], title: "Categoria", "x-ordem": 7 },
    quarto: { oneOf: [{ const: 1, title: "Individual" }, { const: 2, title: "Duplo" }], title: "Quarto", "x-ordem": 8 },
    cafe: { type: "boolean", title: "Café incluso?", "x-ordem": 9 },
  },
};

// Os valores saem pela tela: o teste lê o que o formulário guardou.
const valoresNaTela = (): ValoresCampos => JSON.parse(screen.getByTestId("valores").textContent ?? "{}");

function Formulario({ config }: { config: ConfigTipo }) {
  const [valores, setValores] = useState<ValoresCampos>({});
  const erros = validarCampos("hospedagem", config, valores);
  return (
    <div>
      {config.campos.map((campo) => (
        <CampoDinamico
          key={campo.chave}
          campo={campo}
          valor={valores[campo.chave] ?? ""}
          onChange={(v) => setValores((atual) => ({ ...atual, [campo.chave]: v }))}
          error={valores[campo.chave] !== undefined ? erros[campo.chave] : undefined}
        />
      ))}
      <output data-testid="valores">{JSON.stringify(valores)}</output>
    </div>
  );
}

const input = (rotulo: RegExp) => screen.getByLabelText(rotulo) as HTMLInputElement;

describe("CampoDinamico — um campo por tipo do schema (#365)", () => {
  const config = configDoSchema(SCHEMA);

  it("desenha cada tipo com o controle certo", () => {
    render(<Formulario config={config} />);

    expect(input(/^Hotel/).type).toBe("text");
    expect(screen.getByText("Nome do estabelecimento")).toBeTruthy();
    expect(input(/^Observações/).tagName).toBe("TEXTAREA");
    expect(input(/^Diárias/).type).toBe("number");
    expect(input(/^Diárias/).step).toBe("1");
    expect(input(/^Diárias/).min).toBe("1");
    expect(input(/^Valor da diária/).step).toBe("any");
    expect(input(/^Check-in/).type).toBe("date");
    expect(input(/^Chegada/).type).toBe("datetime-local");

    const categoria = screen.getByLabelText("Categoria") as HTMLSelectElement;
    expect([...categoria.options].map((o) => o.text)).toEqual(["", "simples", "luxo"]);
    const quarto = screen.getByLabelText("Quarto") as HTMLSelectElement;
    expect([...quarto.options].map((o) => o.text)).toEqual(["", "Individual", "Duplo"]);

    const cafe = screen.getByTestId("campo-cafe");
    expect(cafe.textContent).toContain("Café incluso?");
    expect(cafe.querySelectorAll("input[type=radio]").length).toBe(2);
  });

  it("o obrigatório marca o rótulo, e o inteiro abaixo do mínimo mostra o erro no campo", () => {
    render(<Formulario config={config} />);
    expect(screen.getByText("Hotel").closest("label")?.textContent).toContain("*");

    fireEvent.change(input(/^Diárias/), { target: { value: "0" } });
    expect(screen.getByText("Deve ser maior ou igual a 1.")).toBeTruthy();
  });

  it("o que o usuário preenche chega ao campos_json com o tipo do JSON Schema", () => {
    render(<Formulario config={config} />);

    fireEvent.change(input(/^Hotel/), { target: { value: "Pousada do Sertão" } });
    fireEvent.change(input(/^Observações/), { target: { value: "Quarto térreo" } });
    fireEvent.change(input(/^Diárias/), { target: { value: "2" } });
    fireEvent.change(input(/^Valor da diária/), { target: { value: "180.5" } });
    fireEvent.change(input(/^Check-in/), { target: { value: "2026-12-10" } });
    fireEvent.change(input(/^Chegada/), { target: { value: "2026-12-10T14:30" } });
    fireEvent.change(screen.getByLabelText("Categoria"), { target: { value: "luxo" } });
    fireEvent.change(screen.getByLabelText("Quarto"), { target: { value: "2" } });
    fireEvent.click(screen.getByLabelText("Sim"));

    expect(validarCampos("hospedagem", config, valoresNaTela())).toEqual({});
    const json = montarCamposJson(config, valoresNaTela());
    expect(json).toMatchObject({
      hotel: "Pousada do Sertão",
      observacoes: "Quarto térreo",
      diarias: 2,
      valor_diaria: 180.5,
      check_in: "2026-12-10",
      categoria: "luxo",
      quarto: 2,
      cafe: true,
    });
    expect(String(json.chegada)).toMatch(/^2026-12-1\dT\d{2}:\d{2}:00\.000Z$/);
  });
});
