"use client";

import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import {
  AGUA_OPTIONS,
  ENERGIA_OPTIONS,
  SITUACAO_MORADIA_OPTIONS,
  TIPO_MORADIA_OPTIONS,
  withCurrentValue,
} from "../upfFormOptions";
import type { UpfFormData } from "../upfForm";

type StepProps = {
  form: UpfFormData;
  errors: Record<string, string>;
  onChange: (patch: Partial<UpfFormData>) => void;
};

export function MoradiaStep({ form, onChange }: StepProps) {
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <Select
        label="Tipo de moradia"
        options={withCurrentValue(TIPO_MORADIA_OPTIONS, form.tipo_moradia)}
        value={form.tipo_moradia}
        onChange={(v) => onChange({ tipo_moradia: v })}
      />
      <Select
        label="Situação da moradia"
        options={withCurrentValue(SITUACAO_MORADIA_OPTIONS, form.situacao_moradia)}
        value={form.situacao_moradia}
        onChange={(v) => onChange({ situacao_moradia: v })}
      />

      {/* Campos previstos no design mas ainda sem coluna no backend — desabilitados. */}
      <Input
        label="Material"
        disabled
        value=""
        helperText="Indisponível (pendência de backend)."
      />
      <Input
        label="Cômodos"
        disabled
        value=""
        helperText="Indisponível (pendência de backend)."
      />

      <Select
        label="Energia"
        options={withCurrentValue(ENERGIA_OPTIONS, form.energia)}
        value={form.energia}
        onChange={(v) => onChange({ energia: v })}
      />
      <Select
        label="Água"
        options={withCurrentValue(AGUA_OPTIONS, form.agua)}
        value={form.agua}
        onChange={(v) => onChange({ agua: v })}
      />
    </div>
  );
}
