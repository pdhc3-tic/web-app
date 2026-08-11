"use client";

import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { PhotoUploader } from "@/app/components/sgp/PhotoUploader/PhotoUploader";
import { formatCpfInput } from "@/app/lib/format";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";
import { SEGURIDADE_OPTIONS, withCurrentValue } from "../upfFormOptions";
import type { UpfFormData } from "../upfForm";

type StepProps = {
  form: UpfFormData;
  errors: Record<string, string>;
  onChange: (patch: Partial<UpfFormData>) => void;
  /** Presentes apenas em modo edição — a foto depende do id da UPF já existir. */
  upfId?: string;
  fotoUrl?: string | null;
  onPhotoChange?: (url: string | null) => void;
};

export function DadosBasicosStep({
  form,
  errors,
  onChange,
  upfId,
  fotoUrl,
  onPhotoChange,
}: StepProps) {
  const choices = useSgpChoices();

  function toggleSeguridade(value: string) {
    const set = new Set(form.seguridade_social);
    if (set.has(value)) set.delete(value);
    else set.add(value);
    onChange({ seguridade_social: [...set] });
  }

  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <span className="text-label font-medium text-text leading-[1.2]">
          Foto do titular
        </span>
        <div className="mt-2">
          {upfId ? (
            <PhotoUploader
              currentUrl={fotoUrl ?? null}
              onChange={onPhotoChange ?? (() => {})}
              uploadUrlEndpoint={`/api/v1/upfs/${upfId}/foto/upload-url/`}
              confirmEndpoint={`/api/v1/upfs/${upfId}/foto/confirm/`}
              deleteEndpoint={`/api/v1/upfs/${upfId}/foto/`}
            />
          ) : (
            <p className="text-sm text-text-muted">
              Foto pode ser adicionada após o cadastro inicial.
            </p>
          )}
        </div>
      </div>

      <Input
        label="Nome do titular"
        required
        value={form.nome_titular}
        onChange={(e) => onChange({ nome_titular: e.target.value })}
        error={errors.nome_titular}
        className="sm:col-span-2"
      />

      <Input
        id="upf-cpf"
        label="CPF"
        required
        inputMode="numeric"
        maxLength={14}
        placeholder="000.000.000-00"
        value={form.cpf}
        onChange={(e) => onChange({ cpf: formatCpfInput(e.target.value) })}
        error={errors.cpf}
      />
      <Input
        label="RG"
        value={form.rg}
        onChange={(e) => onChange({ rg: e.target.value })}
      />

      <Input
        label="Apelido"
        value={form.apelido}
        onChange={(e) => onChange({ apelido: e.target.value })}
      />
      <Input
        label="Data de nascimento"
        type="date"
        value={form.data_nasc}
        onChange={(e) => onChange({ data_nasc: e.target.value })}
      />

      <Select
        label="Gênero"
        options={withCurrentValue(choices.genero, form.genero)}
        value={form.genero}
        onChange={(v) => onChange({ genero: v })}
      />
      <Select
        label="Cor/Raça"
        options={withCurrentValue(choices.cor_raca, form.cor_raca)}
        value={form.cor_raca}
        onChange={(v) => onChange({ cor_raca: v })}
      />

      <Select
        label="Escolaridade"
        options={withCurrentValue(choices.escolaridade, form.escolaridade)}
        value={form.escolaridade}
        onChange={(v) => onChange({ escolaridade: v })}
      />

      <Select
        label="PCT (povos e comunidades tradicionais)"
        options={withCurrentValue(choices.pct, form.pct)}
        value={form.pct}
        onChange={(v) => onChange({ pct: v })}
      />
      <Select
        label="Posse da terra"
        options={withCurrentValue(choices.posse_terra, form.posse_terra)}
        value={form.posse_terra}
        onChange={(v) => onChange({ posse_terra: v })}
      />

      <Input
        label="NIS"
        inputMode="numeric"
        value={form.nis}
        onChange={(e) => onChange({ nis: e.target.value })}
      />
      <Input
        label="DAP/CAF"
        value={form.daf_caf}
        onChange={(e) => onChange({ daf_caf: e.target.value })}
      />

      <Input
        label="Área da terra (ha)"
        type="number"
        step="0.01"
        min="0"
        value={form.area_terra_ha}
        onChange={(e) => onChange({ area_terra_ha: e.target.value })}
      />

      <fieldset className="sm:col-span-2 flex flex-col gap-1.5">
        <legend className="text-label font-medium text-text leading-[1.2]">
          Seguridade social
        </legend>
        <div className="flex flex-wrap gap-2">
          {SEGURIDADE_OPTIONS.map((o) => {
            const active = form.seguridade_social.includes(o.value);
            return (
              <button
                key={o.value}
                type="button"
                aria-pressed={active}
                onClick={() => toggleSeguridade(o.value)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  active
                    ? "border-primary bg-success-bg text-success-text"
                    : "border-border bg-surface text-text-muted hover:border-text-muted"
                }`}
              >
                {o.label}
              </button>
            );
          })}
        </div>
      </fieldset>
    </div>
  );
}
