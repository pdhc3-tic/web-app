"use client";

import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { Input } from "@/app/components/ui/Input/Input";
import { Label } from "@/app/components/ui/Label/Label";
import { formatCepInput } from "@/app/lib/format";
import { GpsCapture } from "../GpsCapture";
import type { UpfFormData } from "../upfForm";

export const CREATE_COMUNIDADE_VALUE = "__create__";

type LocalizacaoStepProps = {
  form: UpfFormData;
  errors: Record<string, string>;
  onChange: (patch: Partial<UpfFormData>) => void;
  estadoOptions: SelectOption[];
  municipioOptions: SelectOption[];
  comunidadeOptions: SelectOption[];
  projetoOptions: SelectOption[];
  territorioNome: string;
  territorioWarning: boolean;
  onEstadoChange: (value: string) => void;
  onMunicipioChange: (value: string) => void;
  onComunidadeChange: (value: string) => void;
  onGps: (lat: string, lng: string) => void;
};

export function LocalizacaoStep({
  form,
  errors,
  onChange,
  estadoOptions,
  municipioOptions,
  comunidadeOptions,
  projetoOptions,
  territorioNome,
  territorioWarning,
  onEstadoChange,
  onMunicipioChange,
  onComunidadeChange,
  onGps,
}: LocalizacaoStepProps) {
  const comunidadeWithCreate: SelectOption[] = [
    ...comunidadeOptions,
    { value: CREATE_COMUNIDADE_VALUE, label: "+ Criar nova comunidade" },
  ];

  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <Select
        label="Estado"
        required
        options={estadoOptions}
        value={form.estado}
        onChange={onEstadoChange}
        error={errors.estado}
        placeholder="Selecione o estado"
      />

      <Select
        label="Município"
        required
        options={municipioOptions}
        value={form.municipio}
        onChange={onMunicipioChange}
        error={errors.municipio}
        disabled={!form.estado}
        placeholder={form.estado ? "Selecione o município" : "Escolha o estado antes"}
      />

      <Select
        label="Comunidade"
        options={comunidadeWithCreate}
        value={form.comunidade}
        onChange={onComunidadeChange}
        disabled={!form.municipio}
        placeholder={
          form.municipio ? "Selecione a comunidade" : "Escolha o município antes"
        }
      />

      <div className="flex flex-col gap-1">
        <Label htmlFor="upf-territorio">
          Território{" "}
          <span className="text-2xs font-normal text-text-muted">
            (automático)
          </span>
        </Label>
        <div
          id="upf-territorio"
          className="flex h-9 items-center rounded-md border border-border bg-surface-muted px-3 text-sm text-text-muted"
        >
          {territorioNome || (form.municipio ? "Não definido" : "—")}
        </div>
        {territorioWarning && (
          <span className="text-xs text-warning-text" role="alert">
            Este município não tem território vinculado; o cadastro pode falhar
            ao salvar.
          </span>
        )}
      </div>

      <Select
        label="Projeto"
        required
        options={projetoOptions}
        value={form.projeto}
        onChange={(v) => onChange({ projeto: v })}
        placeholder="Selecione o projeto"
        error={errors.projeto}
      />

      <div className="sm:col-span-2">
        <GpsCapture
          latitude={form.latitude}
          longitude={form.longitude}
          onCapture={onGps}
        />
      </div>

      <Input
        label="Logradouro"
        value={form.logradouro}
        onChange={(e) => onChange({ logradouro: e.target.value })}
      />
      <Input
        label="Número"
        value={form.numero}
        onChange={(e) => onChange({ numero: e.target.value })}
      />
      <Input
        label="Complemento"
        value={form.complemento}
        onChange={(e) => onChange({ complemento: e.target.value })}
      />
      <Input
        label="Bairro"
        value={form.bairro}
        onChange={(e) => onChange({ bairro: e.target.value })}
      />
      <Input
        label="CEP"
        inputMode="numeric"
        maxLength={9}
        placeholder="00000-000"
        value={form.cep}
        onChange={(e) => onChange({ cep: formatCepInput(e.target.value) })}
      />
    </div>
  );
}
