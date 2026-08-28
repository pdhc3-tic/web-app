"use client";

import { useEffect, useMemo, useState } from "react";
import { Pencil, X } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { Label } from "@/app/components/ui/Label/Label";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import {
  createMembro,
  updateMembro,
  getMembro,
  calcIdade,
  saudeLabel,
  SAUDE_OPTIONS,
  type MembroDetail,
  type MembroListItem,
  type MembroWritePayload,
} from "@/app/lib/membros";
import { formatCpfInput, isValidCpf, maskCpf } from "@/app/lib/format";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";
import {
  SEGURIDADE_OPTIONS,
  labelForValue,
  withCurrentValue,
} from "@/app/(protected)/sgp/upfs/_components/upfFormOptions";

// ─── Tipos ───────────────────────────────────────────────────────────────────

export type SlideOverMode = "create" | "edit" | "view";

type Props = {
  open: boolean;
  onClose: () => void;
  mode: SlideOverMode;
  upfId: string | number;
  /** Item da tabela (para pré-carregar id/nome enquanto o detalhe carrega). */
  membroListItem?: MembroListItem;
  /**
   * Já existe um titular cadastrado nesta UPF? Usado para desabilitar a opção
   * "Titular" no select — a menos que este próprio membro já seja o titular.
   */
  titularExists: boolean;
  /** Chamado após salvar (create ou edit). Recebe o membro persistido. */
  onSaved: (membro: MembroDetail) => void;
  /** Chamado quando o usuário clica em "Editar" no modo view. */
  onEditFromView?: () => void;
};

type FormState = {
  nome_completo: string;
  grau_parentesco: string;
  data_nascimento: string;
  genero: string;
  cpf: string;
  nis: string;
  caf: string;
  escolaridade: string;
  escola: string;
  cor_raca: string;
  saude: string[];
  seguridade_social: string[];
};

const EMPTY_FORM: FormState = {
  nome_completo: "",
  grau_parentesco: "",
  data_nascimento: "",
  genero: "",
  cpf: "",
  nis: "",
  caf: "",
  escolaridade: "",
  escola: "",
  cor_raca: "",
  saude: [],
  seguridade_social: [],
};

/**
 * Opção que zera as demais em cada multiselect. Espelha validate_saude e
 * validate_seguridade_social em apps/sgp/serializers.py.
 */
const VALOR_EXCLUSIVO: Record<"saude" | "seguridade_social", string> = {
  saude: "nenhuma",
  seguridade_social: "nenhum",
};

/** "" ↔ null para choices inteiros (o form guarda string; a API espera número). */
function intToStr(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : String(value);
}

function strToInt(value: string): number | null {
  return value ? Number(value) : null;
}

function detailToForm(m: MembroDetail): FormState {
  return {
    nome_completo: m.nome_completo ?? "",
    grau_parentesco: m.grau_parentesco ?? "",
    data_nascimento: m.data_nascimento ?? "",
    genero: intToStr(m.genero),
    cpf: m.cpf ? formatCpfInput(m.cpf) : "",
    nis: m.nis ?? "",
    caf: m.caf ?? "",
    escolaridade: intToStr(m.escolaridade),
    escola: m.escola ?? "",
    cor_raca: intToStr(m.cor_raca),
    saude: m.saude ?? [],
    seguridade_social: m.seguridade_social ?? [],
  };
}

function formToPayload(f: FormState): MembroWritePayload {
  const cpfDigits = f.cpf.replace(/\D/g, "");
  return {
    nome_completo: f.nome_completo.trim(),
    grau_parentesco: f.grau_parentesco,
    data_nascimento: f.data_nascimento || null,
    genero: strToInt(f.genero),
    cpf: cpfDigits,
    nis: f.nis.trim(),
    caf: f.caf.trim(),
    escolaridade: strToInt(f.escolaridade),
    escola: f.escola.trim(),
    cor_raca: strToInt(f.cor_raca),
    saude: f.saude,
    seguridade_social: f.seguridade_social,
  };
}

// ─── Componente principal ────────────────────────────────────────────────────

export function MembroSlideOver({
  open,
  onClose,
  mode,
  upfId,
  membroListItem,
  titularExists,
  onSaved,
  onEditFromView,
}: Props) {
  const choices = useSgpChoices();
  const [membro, setMembro] = useState<MembroDetail | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [globalError, setGlobalError] = useState<string | null>(null);

  const membroId = membroListItem?.id;

  // Carrega o detalhe quando abre em modo view/edit. Em create, começa vazio.
  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFieldErrors({});
    setGlobalError(null);

    if (mode === "create") {
      setMembro(null);
      setForm(EMPTY_FORM);
      return;
    }
    if (!membroId) return;

    const controller = new AbortController();
    setLoading(true);
    getMembro(upfId, membroId, controller.signal)
      .then((data) => {
        setMembro(data);
        setForm(detailToForm(data));
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setGlobalError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar o membro.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [open, mode, upfId, membroId]);

  // Idade calculada em tempo real ao lado do campo data_nascimento.
  const idade = useMemo(
    () => calcIdade(form.data_nascimento),
    [form.data_nascimento],
  );

  // Titular só é desabilitado se já existe titular E este membro não é ele.
  const parentescoOptions = useMemo(() => {
    const isCurrentTitular = membro?.grau_parentesco === "titular";
    return choices.grau_parentesco.map((p) => ({
      value: p.value,
      label: p.label,
      disabled: p.value === "titular" && titularExists && !isCurrentTitular,
    }));
  }, [choices.grau_parentesco, titularExists, membro]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setFieldErrors((errs) => {
      if (!(key in errs)) return errs;
      const next = { ...errs };
      delete next[key as string];
      return next;
    });
  }

  /**
   * Alterna um item dos multiselects respeitando a exclusividade validada no
   * backend: marcar "nenhuma"/"nenhum" limpa o resto, e marcar qualquer outra
   * opção descarta a exclusiva. Sem isso o submit voltaria 400.
   */
  function toggleMulti(key: "saude" | "seguridade_social", value: string) {
    setForm((f) => {
      const list = f[key];
      if (list.includes(value)) {
        return { ...f, [key]: list.filter((v) => v !== value) };
      }
      const exclusivo = VALOR_EXCLUSIVO[key];
      const next =
        value === exclusivo
          ? [value]
          : [...list.filter((v) => v !== exclusivo), value];
      return { ...f, [key]: next };
    });
  }

  function validateClient(): boolean {
    const errs: Record<string, string> = {};
    if (!form.nome_completo.trim())
      errs.nome_completo = "Informe o nome.";
    if (!form.grau_parentesco)
      errs.grau_parentesco = "Selecione o parentesco.";
    if (form.cpf.trim() && !isValidCpf(form.cpf)) {
      errs.cpf = "CPF inválido.";
    }
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSave() {
    if (saving) return;
    setGlobalError(null);
    if (!validateClient()) return;

    setSaving(true);
    try {
      const payload = formToPayload(form);
      const saved =
        mode === "edit" && membro
          ? await updateMembro(upfId, membro.id, payload)
          : await createMembro(upfId, payload);
      onSaved(saved);
    } catch (e: unknown) {
      if (e instanceof ApiError) {
        const errs: Record<string, string> = {};
        // FormState usa os mesmos nomes da API — o erro cai direto no campo.
        e.fieldErrors?.forEach((fe) => {
          errs[fe.field] = fe.message;
        });
        setFieldErrors(errs);
        if (!e.fieldErrors || e.fieldErrors.length === 0) {
          setGlobalError(e.message);
        }
      } else {
        setGlobalError("Não foi possível salvar. Tente novamente.");
      }
    } finally {
      setSaving(false);
    }
  }

  const isView = mode === "view";
  const title =
    mode === "create"
      ? "Adicionar membro"
      : mode === "edit"
        ? "Editar membro"
        : membro?.nome_completo || membroListItem?.nome_completo || "Membro";

  const actions = isView && onEditFromView ? (
    <Button
      variant="secondary"
      size="sm"
      leftIcon={<Pencil className="h-3.5 w-3.5" />}
      onClick={onEditFromView}
    >
      Editar
    </Button>
  ) : undefined;

  const footer = isView ? (
    <div className="flex justify-end">
      <Button variant="secondary" onClick={onClose}>
        Fechar
      </Button>
    </div>
  ) : (
    <div className="flex items-center justify-end gap-2">
      <Button variant="ghost" onClick={onClose} disabled={saving}>
        Cancelar
      </Button>
      <Button onClick={handleSave} loading={saving}>
        Salvar
      </Button>
    </div>
  );

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={title}
      actions={actions}
      footer={footer}
      width="wide"
    >
      {loading ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner className="h-6 w-6 animate-spin text-text-muted" />
        </div>
      ) : isView && membro ? (
        <ViewBody membro={membro} />
      ) : (
        <FormBody
          form={form}
          fieldErrors={fieldErrors}
          globalError={globalError}
          idade={idade}
          parentescoOptions={parentescoOptions}
          update={update}
          toggleMulti={toggleMulti}
        />
      )}
    </SlideOver>
  );
}

// ─── Corpo em modo view ──────────────────────────────────────────────────────

function ViewBody({ membro }: { membro: MembroDetail }) {
  const saudeChips =
    membro.saude.length > 0 ? (
      <div className="flex flex-wrap gap-1.5">
        {membro.saude.map((s) => (
          <Chip key={s}>{saudeLabel(s)}</Chip>
        ))}
      </div>
    ) : undefined;

  const seguridadeChips =
    membro.seguridade_social.length > 0 ? (
      <div className="flex flex-wrap gap-1.5">
        {membro.seguridade_social.map((s) => (
          <Chip key={s}>{labelForValue(SEGURIDADE_OPTIONS, s)}</Chip>
        ))}
      </div>
    ) : undefined;

  return (
    <div className="px-4 py-4">
      <DefinitionList
        items={[
          { label: "Nome", value: membro.nome_completo },
          { label: "Parentesco", value: membro.grau_parentesco_display },
          { label: "Nascimento", value: membro.data_nascimento ?? undefined },
          {
            label: "Idade",
            value:
              membro.idade !== null && membro.idade !== undefined
                ? `${membro.idade} anos`
                : undefined,
          },
          { label: "Gênero", value: membro.genero_display },
          { label: "Cor/Raça", value: membro.cor_raca_display },
          { label: "CPF", value: maskCpf(membro.cpf) },
          { label: "NIS", value: membro.nis },
          { label: "CAF", value: membro.caf },
          { label: "Escolaridade", value: membro.escolaridade_display },
          { label: "Escola", value: membro.escola },
          { label: "Saúde", value: saudeChips },
          { label: "Seguridade", value: seguridadeChips },
        ]}
      />
    </div>
  );
}

// ─── Corpo em modo create/edit ───────────────────────────────────────────────

type FormBodyProps = {
  form: FormState;
  fieldErrors: Record<string, string>;
  globalError: string | null;
  idade: number | null;
  parentescoOptions: { value: string; label: string; disabled?: boolean }[];
  update: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
  toggleMulti: (key: "saude" | "seguridade_social", value: string) => void;
};

function FormBody({
  form,
  fieldErrors,
  globalError,
  idade,
  parentescoOptions,
  update,
  toggleMulti,
}: FormBodyProps) {
  const choices = useSgpChoices();
  return (
    <div className="flex flex-col gap-4 px-4 py-4">
      {globalError && (
        <div
          role="alert"
          className="rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text"
        >
          {globalError}
        </div>
      )}

      <Input
        label="Nome completo"
        required
        value={form.nome_completo}
        onChange={(e) => update("nome_completo", e.target.value)}
        error={fieldErrors.nome_completo}
        autoComplete="off"
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <SelectField
          label="Parentesco"
          required
          value={form.grau_parentesco}
          onChange={(v) => update("grau_parentesco", v)}
          options={parentescoOptions}
          error={fieldErrors.grau_parentesco}
          placeholder="Selecione..."
        />

        <div className="flex flex-col gap-1">
          <Input
            label="Data de nascimento"
            type="date"
            value={form.data_nascimento}
            onChange={(e) => update("data_nascimento", e.target.value)}
            error={fieldErrors.data_nascimento}
          />
          {idade !== null && (
            <span className="text-xs text-text-muted">{idade} anos</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Select
          label="Gênero"
          value={form.genero}
          onChange={(v) => update("genero", v)}
          options={withCurrentValue(choices.genero, form.genero)}
          error={fieldErrors.genero}
          placeholder="Selecione..."
        />
        <Select
          label="Cor/Raça"
          value={form.cor_raca}
          onChange={(v) => update("cor_raca", v)}
          options={withCurrentValue(choices.cor_raca, form.cor_raca)}
          error={fieldErrors.cor_raca}
          placeholder="Selecione..."
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Input
          label="CPF"
          value={form.cpf}
          onChange={(e) => update("cpf", formatCpfInput(e.target.value))}
          error={fieldErrors.cpf}
          placeholder="000.000.000-00"
          inputMode="numeric"
          autoComplete="off"
        />
        <Input
          label="NIS"
          value={form.nis}
          onChange={(e) => update("nis", e.target.value.replace(/\D/g, ""))}
          error={fieldErrors.nis}
          inputMode="numeric"
          maxLength={11}
        />
        <Input
          label="CAF"
          value={form.caf}
          onChange={(e) => update("caf", e.target.value)}
          error={fieldErrors.caf}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Select
          label="Escolaridade"
          value={form.escolaridade}
          onChange={(v) => update("escolaridade", v)}
          options={withCurrentValue(choices.escolaridade, form.escolaridade)}
          error={fieldErrors.escolaridade}
          placeholder="Selecione..."
        />
        <Input
          label="Escola"
          value={form.escola}
          onChange={(e) => update("escola", e.target.value)}
          error={fieldErrors.escola}
        />
      </div>

      <MultiSelect
        label="Saúde"
        selected={form.saude}
        options={SAUDE_OPTIONS}
        onToggle={(v) => toggleMulti("saude", v)}
        error={fieldErrors.saude}
      />

      <MultiSelect
        label="Seguridade social"
        selected={form.seguridade_social}
        options={SEGURIDADE_OPTIONS}
        onToggle={(v) => toggleMulti("seguridade_social", v)}
        error={fieldErrors.seguridade_social}
      />
    </div>
  );
}

// ─── SelectField com suporte a option.disabled ───────────────────────────────
// O componente <Select> nativo do design system não expõe disabled por-opção;
// para essa necessidade específica (Titular já existente) usamos um <select>
// HTML estilizado com as mesmas classes de aparência.

function SelectField({
  label,
  required,
  value,
  onChange,
  options,
  error,
  placeholder,
}: {
  label: string;
  required?: boolean;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string; disabled?: boolean }[];
  error?: string;
  placeholder?: string;
}) {
  const id = `sf-${label.replace(/\s+/g, "-").toLowerCase()}`;
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id} required={required}>
        {label}
      </Label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={!!error || undefined}
        className={`h-9 w-full rounded-md border bg-surface px-3 text-sm text-text outline-none transition duration-120 hover:border-text-muted focus:border-2 focus:border-primary focus:px-[calc(var(--space-3)-1px)] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-primary)_15%,transparent)] ${
          error
            ? "border-error-text focus:border-error-text focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--color-error-text)_15%,transparent)]"
            : "border-border"
        }`}
      >
        {placeholder && (
          <option value="" disabled={required}>
            {placeholder}
          </option>
        )}
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
            {o.disabled ? " (já existe)" : ""}
          </option>
        ))}
      </select>
      {error && (
        <span className="text-xs text-error-text">{error}</span>
      )}
    </div>
  );
}

// ─── Multi-select em chips ───────────────────────────────────────────────────

function MultiSelect({
  label,
  selected,
  options,
  onToggle,
  error,
}: {
  label: string;
  selected: string[];
  options: { value: string; label: string }[];
  onToggle: (value: string) => void;
  error?: string;
}) {
  const id = `ms-${label.replace(/\s+/g, "-").toLowerCase()}`;
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>

      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map((v) => {
            const opt = options.find((o) => o.value === v);
            return (
              <button
                key={v}
                type="button"
                onClick={() => onToggle(v)}
                className="inline-flex items-center gap-1 rounded-full border border-primary bg-primary/10 px-2 py-0.5 text-2xs font-medium text-primary transition hover:bg-primary/15"
                aria-label={`Remover ${opt?.label ?? v}`}
              >
                {opt?.label ?? v}
                <X className="h-3 w-3" />
              </button>
            );
          })}
        </div>
      )}

      <div
        id={id}
        role="group"
        aria-label={label}
        className="flex flex-wrap gap-1.5"
      >
        {options
          .filter((o) => !selected.includes(o.value))
          .map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => onToggle(o.value)}
              className="inline-flex items-center rounded-full border border-border bg-surface px-2 py-0.5 text-2xs font-medium text-text-muted transition hover:border-primary hover:text-primary"
            >
              + {o.label}
            </button>
          ))}
      </div>

      {error && <span className="text-xs text-error-text">{error}</span>}
    </div>
  );
}
