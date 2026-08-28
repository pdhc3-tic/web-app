"use client";

import { Input } from "@/app/components/ui/Input/Input";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";

export type SyncEventsFiltrosValue = {
  /** YYYY-MM-DD (input nativo). */
  de: string;
  ate: string;
  /** Id do dispositivo como string; "" = todos. */
  device: string;
  /** Só eventos com erros. */
  comErro: boolean;
};

type Props = {
  value: SyncEventsFiltrosValue;
  onChange: (next: SyncEventsFiltrosValue) => void;
  dispositivoOptions: SelectOption[];
  disabled?: boolean;
};

/**
 * Filtros do log de sincronização (#157). "Técnico/dispositivo" do critério
 * é atendido pelo select de dispositivo — cada dispositivo já pertence a um
 * técnico único no seed (round-robin), então filtrar por dispositivo é o
 * caminho natural. Uma pesquisa por técnico independente exigiria um endpoint
 * dedicado a listar técnicos (não existe hoje).
 */
export function SyncEventsFiltros({
  value,
  onChange,
  dispositivoOptions,
  disabled,
}: Props) {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_minmax(0,2fr)]">
        <Input
          label="De"
          type="date"
          value={value.de}
          onChange={(e) => onChange({ ...value, de: e.target.value })}
          max={value.ate || undefined}
          disabled={disabled}
        />
        <Input
          label="Até"
          type="date"
          value={value.ate}
          onChange={(e) => onChange({ ...value, ate: e.target.value })}
          min={value.de || undefined}
          disabled={disabled}
        />
        <Select
          label="Dispositivo"
          value={value.device}
          onChange={(v) => onChange({ ...value, device: v })}
          options={[{ value: "", label: "Todos" }, ...dispositivoOptions]}
          disabled={disabled}
        />
      </div>

      <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-text-muted">
        <input
          type="checkbox"
          checked={value.comErro}
          onChange={(e) => onChange({ ...value, comErro: e.target.checked })}
          disabled={disabled}
          className="h-4 w-4 accent-primary"
          data-testid="sync-events-filtro-com-erro"
        />
        Apenas eventos com erros
      </label>
    </div>
  );
}
