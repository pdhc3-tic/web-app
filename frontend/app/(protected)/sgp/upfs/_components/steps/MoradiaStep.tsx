"use client";

import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";
import { withCurrentValue } from "../upfFormOptions";
import type { UpfFormData } from "../upfForm";

type StepProps = {
  form: UpfFormData;
  errors: Record<string, string>;
  onChange: (patch: Partial<UpfFormData>) => void;
};

export function MoradiaStep({ form, errors, onChange }: StepProps) {
  const choices = useSgpChoices();

  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <Select
        label="Tipo de moradia"
        options={withCurrentValue(choices.tipo_moradia, form.tipo_moradia)}
        value={form.tipo_moradia}
        onChange={(v) => onChange({ tipo_moradia: v })}
      />
      <Select
        label="Situação da moradia"
        options={withCurrentValue(choices.situacao_moradia, form.situacao_moradia)}
        value={form.situacao_moradia}
        onChange={(v) => onChange({ situacao_moradia: v })}
      />

      <Select
        label="Material de construção"
        options={withCurrentValue(choices.material_construcao, form.material_construcao)}
        value={form.material_construcao}
        onChange={(v) => onChange({ material_construcao: v })}
      />
      <Input
        label="Número de cômodos"
        type="number"
        min="0"
        inputMode="numeric"
        value={form.num_comodos}
        onChange={(e) => onChange({ num_comodos: e.target.value })}
        error={errors.num_comodos}
      />

      <Select
        label="Energia"
        options={withCurrentValue(choices.energia, form.energia)}
        value={form.energia}
        onChange={(v) => onChange({ energia: v })}
      />
      <Select
        label="Água"
        options={withCurrentValue(choices.agua, form.agua)}
        value={form.agua}
        onChange={(v) => onChange({ agua: v })}
      />
    </div>
  );
}
