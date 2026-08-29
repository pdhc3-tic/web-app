"use client";

import { Input } from "@/app/components/ui/Input/Input";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";

export type FormulariosFiltrosValue = {
  /** Id do formulário selecionado como string; "" = todos. */
  formulario_id: string;
  /** YYYY-MM-DD do input nativo. Enviado direto ao BE-16 (date__gte/date__lte). */
  data_inicio: string;
  data_fim: string;
  /** Busca `icontains` no BE. */
  respondente: string;
};

type Props = {
  value: FormulariosFiltrosValue;
  onChange: (next: FormulariosFiltrosValue) => void;
  formularioOptions: SelectOption[];
  disabled?: boolean;
};

/**
 * Filtros da aba Formulários (#180).
 *
 * As opções do select de formulário vêm da própria listagem de respostas
 * daquela UPF — o critério diz "formulários que já têm ao menos uma resposta
 * vinculada". A extração é feita no container (FormulariosTab), aqui só
 * recebemos as options prontas.
 */
export function FormulariosFiltros({
  value,
  onChange,
  formularioOptions,
  disabled,
}: Props) {
  return (
    <div
      className="grid grid-cols-1 gap-3 sm:grid-cols-[2fr_1fr_1fr_2fr]"
      data-testid="formularios-filtros"
    >
      <Select
        label="Formulário"
        value={value.formulario_id}
        onChange={(v) => onChange({ ...value, formulario_id: v })}
        options={[{ value: "", label: "Todos" }, ...formularioOptions]}
        disabled={disabled}
      />
      <Input
        label="De"
        type="date"
        value={value.data_inicio}
        onChange={(e) => onChange({ ...value, data_inicio: e.target.value })}
        max={value.data_fim || undefined}
        disabled={disabled}
      />
      <Input
        label="Até"
        type="date"
        value={value.data_fim}
        onChange={(e) => onChange({ ...value, data_fim: e.target.value })}
        min={value.data_inicio || undefined}
        disabled={disabled}
      />
      <Input
        label="Respondente"
        type="search"
        value={value.respondente}
        onChange={(e) => onChange({ ...value, respondente: e.target.value })}
        placeholder="Nome do respondente"
        disabled={disabled}
      />
    </div>
  );
}
