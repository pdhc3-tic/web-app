"use client";

import { Search } from "lucide-react";
import { Input } from "@/app/components/ui/Input/Input";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";

export type DispositivosFiltrosValue = {
  /** Busca por nome/e-mail do técnico (backend `search`). */
  search: string;
  /** Id do território como string (`""` = todos). */
  territorio: string;
};

type Props = {
  value: DispositivosFiltrosValue;
  onChange: (next: DispositivosFiltrosValue) => void;
  territorioOptions: SelectOption[];
  disabled?: boolean;
};

/**
 * Barra de filtros do painel de dispositivos (#156).
 * O campo "Técnico" da issue é um search por nome/e-mail — o backend suporta
 * `search` em user__nome/user__email; um dropdown por técnico exigiria um
 * endpoint dedicado, fora do escopo atual.
 */
export function DispositivosFiltros({
  value,
  onChange,
  territorioOptions,
  disabled,
}: Props) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,1fr)_240px]">
      <Input
        label="Técnico"
        placeholder="Nome ou e-mail"
        value={value.search}
        onChange={(e) => onChange({ ...value, search: e.target.value })}
        startIcon={<Search className="h-4 w-4" />}
        disabled={disabled}
      />
      <Select
        label="Território"
        value={value.territorio}
        onChange={(v) => onChange({ ...value, territorio: v })}
        options={[{ value: "", label: "Todos" }, ...territorioOptions]}
        disabled={disabled}
      />
    </div>
  );
}
