"use client";

import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { formatPhoneInput } from "@/app/lib/format";
import { DISPOSITIVO_OPTIONS, withCurrentValue } from "../upfFormOptions";
import type { UpfFormData } from "../upfForm";

type StepProps = {
  form: UpfFormData;
  errors: Record<string, string>;
  onChange: (patch: Partial<UpfFormData>) => void;
};

const INTERNET_OPTIONS = [
  { value: "sim", label: "Sim" },
  { value: "nao", label: "Não" },
];

export function ComunicacaoStep({ form, errors, onChange }: StepProps) {
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <Input
        label="Telefone"
        inputMode="tel"
        maxLength={15}
        placeholder="(00) 00000-0000"
        value={form.telefone}
        onChange={(e) => onChange({ telefone: formatPhoneInput(e.target.value) })}
        error={errors.telefone}
      />
      <Input
        label="WhatsApp"
        inputMode="tel"
        maxLength={15}
        placeholder="(00) 00000-0000"
        value={form.whatsapp}
        onChange={(e) => onChange({ whatsapp: formatPhoneInput(e.target.value) })}
        error={errors.whatsapp}
      />

      <Input
        label="E-mail"
        type="email"
        value={form.email}
        onChange={(e) => onChange({ email: e.target.value })}
        error={errors.email}
      />
      <Select
        label="Acesso à internet"
        options={INTERNET_OPTIONS}
        value={form.internet ? "sim" : "nao"}
        onChange={(v) => onChange({ internet: v === "sim" })}
      />

      <Select
        label="Dispositivo"
        options={withCurrentValue(DISPOSITIVO_OPTIONS, form.dispositivo)}
        value={form.dispositivo}
        onChange={(v) => onChange({ dispositivo: v })}
      />
    </div>
  );
}
