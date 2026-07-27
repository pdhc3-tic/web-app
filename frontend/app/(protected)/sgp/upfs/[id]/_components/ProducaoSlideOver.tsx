"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { CatalogoCombobox } from "./CatalogoCombobox";
import {
  createProducaoMock,
  searchCulturasMock,
  searchEspeciesMock,
  updateProducaoMock,
} from "./producaoMock";
import {
  SISTEMA_CRIACAO_OPTIONS,
  TIPO_OPTIONS,
  TIPO_OUTRA_OPTIONS,
  type CatalogoItem,
  type Producao,
  type ProducaoWritePayload,
  type SistemaCriacao,
  type TipoOutra,
  type TipoProducao,
} from "./producaoTypes";

export type SlideOverMode = "create" | "edit";

type Props = {
  open: boolean;
  onClose: () => void;
  mode: SlideOverMode;
  upfId: string;
  producao?: Producao;
  onSaved: (saved: Producao) => void;
};

type FormState = {
  tipo: TipoProducao | "";
  cultura: CatalogoItem | null;
  area_ha: string;
  producao_estimada: string;
  unidade_producao: string;
  sementes_crioulas: boolean;
  especie: CatalogoItem | null;
  n_matrizes: string;
  n_reprodutores: string;
  n_jovens: string;
  area_pastejo_ha: string;
  sistema_criacao: SistemaCriacao | "";
  tipo_outra: TipoOutra | "";
  descricao_outra: string;
  quantidade_produzida: string;
  renda_estimada_mensal: string;
  custo_anual: string;
  observacoes: string;
};

const EMPTY: FormState = {
  tipo: "",
  cultura: null,
  area_ha: "",
  producao_estimada: "",
  unidade_producao: "",
  sementes_crioulas: false,
  especie: null,
  n_matrizes: "",
  n_reprodutores: "",
  n_jovens: "",
  area_pastejo_ha: "",
  sistema_criacao: "",
  tipo_outra: "",
  descricao_outra: "",
  quantidade_produzida: "",
  renda_estimada_mensal: "",
  custo_anual: "",
  observacoes: "",
};

const numOrNull = (v: string) => {
  const n = Number(v.trim());
  return v.trim() && Number.isFinite(n) ? n : null;
};

const decOrNull = (v: string) => {
  const s = v.trim().replace(",", ".");
  const n = Number(s);
  return s && Number.isFinite(n) ? String(n) : null;
};

function producaoToForm(p: Producao): FormState {
  return {
    tipo: p.tipo,
    cultura: p.cultura,
    area_ha: p.area_ha ?? "",
    producao_estimada: p.producao_estimada ?? "",
    unidade_producao: p.unidade_producao ?? "",
    sementes_crioulas: p.sementes_crioulas,
    especie: p.especie,
    n_matrizes: p.n_matrizes != null ? String(p.n_matrizes) : "",
    n_reprodutores: p.n_reprodutores != null ? String(p.n_reprodutores) : "",
    n_jovens: p.n_jovens != null ? String(p.n_jovens) : "",
    area_pastejo_ha: p.area_pastejo_ha ?? "",
    sistema_criacao: p.sistema_criacao ?? "",
    tipo_outra: p.tipo_outra ?? "",
    descricao_outra: p.descricao_outra ?? "",
    quantidade_produzida: p.quantidade_produzida ?? "",
    renda_estimada_mensal: p.renda_estimada_mensal ?? "",
    custo_anual: p.custo_anual ?? "",
    observacoes: p.observacoes ?? "",
  };
}

function formToPayload(f: FormState): ProducaoWritePayload {
  const tipo = f.tipo as TipoProducao;
  const base: ProducaoWritePayload = {
    tipo,
    custo_anual: decOrNull(f.custo_anual),
    observacoes: f.observacoes.trim() || null,
  };
  if (tipo === "agricola") {
    return {
      ...base,
      cultura_id: f.cultura?.id ?? null,
      area_ha: decOrNull(f.area_ha),
      producao_estimada: decOrNull(f.producao_estimada),
      unidade_producao: f.unidade_producao.trim() || null,
      sementes_crioulas: f.sementes_crioulas,
    };
  }
  if (tipo === "pecuaria") {
    return {
      ...base,
      especie_id: f.especie?.id ?? null,
      n_matrizes: numOrNull(f.n_matrizes),
      n_reprodutores: numOrNull(f.n_reprodutores),
      n_jovens: numOrNull(f.n_jovens),
      area_pastejo_ha: decOrNull(f.area_pastejo_ha),
      sistema_criacao: f.sistema_criacao || null,
    };
  }
  return {
    ...base,
    tipo_outra: f.tipo_outra || null,
    descricao_outra: f.descricao_outra.trim() || null,
    quantidade_produzida: f.quantidade_produzida.trim() || null,
    renda_estimada_mensal: decOrNull(f.renda_estimada_mensal),
  };
}

function hasTipoValues(f: FormState): boolean {
  if (f.tipo === "agricola") {
    return !!(f.cultura || f.area_ha || f.producao_estimada || f.unidade_producao || f.sementes_crioulas);
  }
  if (f.tipo === "pecuaria") {
    return !!(f.especie || f.n_matrizes || f.n_reprodutores || f.n_jovens || f.area_pastejo_ha || f.sistema_criacao);
  }
  if (f.tipo === "outra") {
    return !!(f.tipo_outra || f.descricao_outra || f.quantidade_produzida || f.renda_estimada_mensal);
  }
  return false;
}

export function ProducaoSlideOver({ open, onClose, mode, upfId, producao, onSaved }: Props) {
  const [form, setForm] = useState<FormState>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [globalError, setGlobalError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setErrors({});
    setGlobalError(null);
    setForm(mode === "edit" && producao ? producaoToForm(producao) : EMPTY);
  }, [open, mode, producao]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => {
      if (!(key in e)) return e;
      const next = { ...e };
      delete next[key as string];
      return next;
    });
  }

  function handleTipoChange(next: TipoProducao) {
    if (form.tipo === next) return;
    if (form.tipo && hasTipoValues(form)) {
      const ok = window.confirm("Os dados específicos do tipo anterior serão perdidos. Continuar?");
      if (!ok) return;
    }
    setForm({ ...EMPTY, tipo: next, custo_anual: form.custo_anual, observacoes: form.observacoes });
    setErrors({});
  }

  async function handleSave() {
    if (saving) return;
    setGlobalError(null);
    const errs: Record<string, string> = {};
    if (!form.tipo) errs.tipo = "Selecione o tipo.";
    else if (form.tipo === "agricola" && !form.cultura) errs.cultura = "Selecione a cultura.";
    else if (form.tipo === "pecuaria" && !form.especie) errs.especie = "Selecione a espécie.";
    else if (form.tipo === "outra" && !form.tipo_outra) errs.tipo_outra = "Selecione o tipo de atividade.";
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setSaving(true);
    try {
      const payload = formToPayload(form);
      const saved =
        mode === "edit" && producao
          ? await updateProducaoMock(upfId, producao.id, payload)
          : await createProducaoMock(upfId, payload);
      onSaved(saved);
    } catch {
      setGlobalError("Não foi possível salvar. Tente novamente.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={mode === "create" ? "Nova atividade produtiva" : "Editar atividade produtiva"}
      width="wide"
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>Cancelar</Button>
          <Button onClick={handleSave} loading={saving}>Salvar</Button>
        </div>
      }
    >
      <div className="flex flex-col gap-5 px-4 py-4">
        {globalError && (
          <div role="alert" className="rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text">
            {globalError}
          </div>
        )}

        <TipoPicker value={form.tipo} onChange={handleTipoChange} error={errors.tipo} locked={mode === "edit"} />

        {form.tipo === "agricola" && (
          <div className="flex flex-col gap-4">
            <CatalogoCombobox
              label="Cultura"
              required
              value={form.cultura}
              onChange={(v) => update("cultura", v)}
              search={searchCulturasMock}
              placeholder="Buscar cultura..."
              error={errors.cultura}
            />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Input label="Área (ha)" value={form.area_ha} onChange={(e) => update("area_ha", e.target.value)} inputMode="decimal" placeholder="0,00" />
              <Input label="Produção estimada" value={form.producao_estimada} onChange={(e) => update("producao_estimada", e.target.value)} inputMode="decimal" placeholder="0" />
              <Input label="Unidade" value={form.unidade_producao} onChange={(e) => update("unidade_producao", e.target.value)} placeholder="sacas, kg, ton..." />
            </div>
            <Checkbox label="Sementes crioulas" checked={form.sementes_crioulas} onChange={(v) => update("sementes_crioulas", v)} />
          </div>
        )}

        {form.tipo === "pecuaria" && (
          <div className="flex flex-col gap-4">
            <CatalogoCombobox
              label="Espécie"
              required
              value={form.especie}
              onChange={(v) => update("especie", v)}
              search={searchEspeciesMock}
              placeholder="Buscar espécie..."
              error={errors.especie}
            />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Input label="Matrizes" value={form.n_matrizes} onChange={(e) => update("n_matrizes", e.target.value.replace(/\D/g, ""))} inputMode="numeric" />
              <Input label="Reprodutores" value={form.n_reprodutores} onChange={(e) => update("n_reprodutores", e.target.value.replace(/\D/g, ""))} inputMode="numeric" />
              <Input label="Jovens" value={form.n_jovens} onChange={(e) => update("n_jovens", e.target.value.replace(/\D/g, ""))} inputMode="numeric" />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input label="Área de pastejo (ha)" value={form.area_pastejo_ha} onChange={(e) => update("area_pastejo_ha", e.target.value)} inputMode="decimal" placeholder="0,00" />
              <Select
                label="Sistema de criação"
                value={form.sistema_criacao}
                onChange={(v) => update("sistema_criacao", v as SistemaCriacao | "")}
                options={SISTEMA_CRIACAO_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                placeholder="Selecione..."
              />
            </div>
          </div>
        )}

        {form.tipo === "outra" && (
          <div className="flex flex-col gap-4">
            <Select
              label="Tipo de atividade"
              required
              value={form.tipo_outra}
              onChange={(v) => update("tipo_outra", v as TipoOutra | "")}
              options={TIPO_OUTRA_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
              placeholder="Selecione..."
              error={errors.tipo_outra}
            />
            <Textarea label="Descrição" rows={3} value={form.descricao_outra} onChange={(e) => update("descricao_outra", e.target.value)} placeholder="Descreva a atividade..." />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input label="Quantidade produzida" value={form.quantidade_produzida} onChange={(e) => update("quantidade_produzida", e.target.value)} placeholder="Ex.: 60 unid/mês" />
              <Input label="Renda estimada mensal (R$)" value={form.renda_estimada_mensal} onChange={(e) => update("renda_estimada_mensal", e.target.value)} inputMode="decimal" placeholder="0,00" />
            </div>
          </div>
        )}

        {form.tipo && (
          <div className="flex flex-col gap-4 border-t border-border pt-4">
            <Input label="Custo anual (R$)" value={form.custo_anual} onChange={(e) => update("custo_anual", e.target.value)} inputMode="decimal" placeholder="0,00" />
            <Textarea label="Observações" rows={3} value={form.observacoes} onChange={(e) => update("observacoes", e.target.value)} />
          </div>
        )}
      </div>
    </SlideOver>
  );
}

function TipoPicker({
  value,
  onChange,
  error,
  locked,
}: {
  value: FormState["tipo"];
  onChange: (v: TipoProducao) => void;
  error?: string;
  locked?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-label font-medium text-text">
        Tipo de atividade{locked ? " (não pode ser alterado)" : ""}
      </span>
      <div role="radiogroup" aria-label="Tipo de atividade" className="grid grid-cols-3 gap-2">
        {TIPO_OPTIONS.map((opt) => {
          const active = value === opt.value;
          const disabled = locked && !active;
          return (
            <button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={active}
              disabled={disabled}
              onClick={() => onChange(opt.value)}
              className={[
                "flex h-11 items-center justify-center rounded-md border px-3 text-sm font-medium transition",
                active
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-surface text-text-muted hover:border-text-muted hover:text-text",
                disabled ? "cursor-not-allowed opacity-50" : "",
              ].join(" ")}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      {error && <span className="text-xs text-error-text">{error}</span>}
    </div>
  );
}

function Checkbox({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer select-none items-center gap-2 text-sm text-text">
      <span
        aria-hidden="true"
        className={`flex h-4 w-4 items-center justify-center rounded border transition ${
          checked ? "border-primary bg-primary text-white" : "border-border bg-surface"
        }`}
      >
        {checked && <Check className="h-3 w-3" />}
      </span>
      <input type="checkbox" className="sr-only" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}
