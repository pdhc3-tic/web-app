"use client";

import { useEffect, useState } from "react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import {
  META_NUMERO_OPTIONS,
  createMeta,
  getMeta,
  updateMeta,
  type MetaDetail,
  type MetaListItem,
  type MetaWritePayload,
} from "@/app/lib/metas";
import { OdsPicker } from "./OdsPicker";

// ─── Tipos ───────────────────────────────────────────────────────────────────

export type MetaSlideOverMode = "create" | "edit";

type Props = {
  open: boolean;
  onClose: () => void;
  mode: MetaSlideOverMode;
  /** Item da listagem; em "edit" dispara a busca do detalhe ao abrir. */
  metaListItem?: MetaListItem;
  /** Chamado após salvar (create ou edit), com a Meta persistida. */
  onSaved: (meta: MetaDetail, mode: MetaSlideOverMode) => void;
};

type FormState = {
  /** String porque vem do <Select>; convertido em formToPayload. */
  numero: string;
  titulo: string;
  descricao: string;
  ods_ids: number[];
  data_inicio: string;
  data_fim: string;
};

const EMPTY_FORM: FormState = {
  numero: "",
  titulo: "",
  descricao: "",
  ods_ids: [],
  data_inicio: "",
  data_fim: "",
};

function detailToForm(m: MetaDetail): FormState {
  return {
    numero: String(m.numero),
    titulo: m.titulo ?? "",
    descricao: m.descricao ?? "",
    ods_ids: m.ods_ids ?? [],
    data_inicio: m.data_inicio ?? "",
    data_fim: m.data_fim ?? "",
  };
}

function formToPayload(f: FormState): MetaWritePayload {
  return {
    numero: Number(f.numero),
    titulo: f.titulo.trim(),
    descricao: f.descricao.trim(),
    ods_ids: f.ods_ids,
    data_inicio: f.data_inicio,
    data_fim: f.data_fim,
  };
}

/**
 * Validação de cliente — só o que dá para checar sem ida ao servidor. As regras
 * de domínio (intervalo 1–7, unicidade do número, ODS válidos) ficam no backend
 * e voltam como field_errors.
 */
function validate(f: FormState): Record<string, string> {
  const errs: Record<string, string> = {};
  if (!f.numero) errs.numero = "Selecione o número da Meta.";
  if (!f.titulo.trim()) errs.titulo = "Informe o título da Meta.";
  if (!f.data_inicio) errs.data_inicio = "Informe a data de início.";
  if (!f.data_fim) errs.data_fim = "Informe a data de término.";
  // Comparação lexicográfica é segura para "YYYY-MM-DD".
  if (f.data_inicio && f.data_fim && f.data_fim < f.data_inicio) {
    errs.data_fim = "A data de término não pode ser anterior à de início.";
  }
  return errs;
}

// ─── Componente principal ────────────────────────────────────────────────────

export function MetaSlideOver({
  open,
  onClose,
  mode,
  metaListItem,
  onSaved,
}: Props) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [globalError, setGlobalError] = useState<string | null>(null);

  const metaId = metaListItem?.id;

  // Carrega o detalhe ao abrir em modo edit — a listagem não traz descrição
  // nem ODS. Em create, começa vazio.
  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFieldErrors({});
    setGlobalError(null);

    if (mode === "create") {
      setForm(EMPTY_FORM);
      return;
    }
    if (!metaId) return;

    const controller = new AbortController();
    setLoading(true);
    getMeta(metaId, controller.signal)
      .then((data) => setForm(detailToForm(data)))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setGlobalError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar a Meta.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [open, mode, metaId]);

  function update<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setFieldErrors((prev) => {
      if (!(field in prev)) return prev;
      const next = { ...prev };
      delete next[field as string];
      return next;
    });
  }

  async function handleSave() {
    if (saving) return;

    const errs = validate(form);
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      setGlobalError("Corrija os campos destacados e tente novamente.");
      return;
    }

    setFieldErrors({});
    setGlobalError(null);
    setSaving(true);

    try {
      const payload = formToPayload(form);
      const salva =
        mode === "edit" && metaId
          ? await updateMeta(metaId, payload)
          : await createMeta(payload);
      onSaved(salva, mode);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.fieldErrors?.length) {
        const mapped: Record<string, string> = {};
        for (const fe of e.fieldErrors) mapped[fe.field] = fe.message;
        setFieldErrors(mapped);
        setGlobalError(e.message);
        return;
      }
      setGlobalError(
        e instanceof ApiError
          ? e.message
          : "Não foi possível salvar a Meta. Tente novamente.",
      );
    } finally {
      setSaving(false);
    }
  }

  const title =
    mode === "edit"
      ? `Editar Meta${metaListItem ? ` ${metaListItem.numero}` : ""}`
      : "Nova Meta";

  const footer = (
    <div className="flex items-center justify-end gap-2">
      <Button variant="ghost" onClick={onClose} disabled={saving}>
        Cancelar
      </Button>
      <Button
        onClick={handleSave}
        loading={saving}
        disabled={loading}
        data-testid="meta-form-submit"
      >
        Salvar
      </Button>
    </div>
  );

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={title}
      footer={footer}
      width="wide"
    >
      {loading ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner className="h-6 w-6 animate-spin text-text-muted" />
        </div>
      ) : (
        <FormBody
          form={form}
          fieldErrors={fieldErrors}
          globalError={globalError}
          saving={saving}
          update={update}
        />
      )}
    </SlideOver>
  );
}

// ─── Corpo do formulário ─────────────────────────────────────────────────────

type FormBodyProps = {
  form: FormState;
  fieldErrors: Record<string, string>;
  globalError: string | null;
  saving: boolean;
  update: <K extends keyof FormState>(field: K, value: FormState[K]) => void;
};

function FormBody({
  form,
  fieldErrors,
  globalError,
  saving,
  update,
}: FormBodyProps) {
  return (
    <div className="flex flex-col gap-4 px-4 py-4" data-testid="meta-form">
      {globalError && (
        <div
          role="alert"
          className="rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text"
        >
          {globalError}
        </div>
      )}

      <div data-testid="meta-form-numero">
        <Select
          label="Número"
          required
          options={META_NUMERO_OPTIONS}
          value={form.numero}
          onChange={(v) => update("numero", v)}
          placeholder="Selecione..."
          helperText="O PDHC III tem 7 Metas; cada número pode ser usado uma única vez."
          error={fieldErrors.numero}
          disabled={saving}
        />
      </div>

      <Input
        label="Título"
        required
        maxLength={255}
        value={form.titulo}
        onChange={(e) => update("titulo", e.target.value)}
        error={fieldErrors.titulo}
        disabled={saving}
        autoComplete="off"
        data-testid="meta-form-titulo"
      />

      <Textarea
        label="Descrição"
        rows={4}
        value={form.descricao}
        onChange={(e) => update("descricao", e.target.value)}
        error={fieldErrors.descricao}
        disabled={saving}
        data-testid="meta-form-descricao"
      />

      <OdsPicker
        value={form.ods_ids}
        onChange={(v) => update("ods_ids", v)}
        error={fieldErrors.ods_ids}
        disabled={saving}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Input
          label="Data de início"
          type="date"
          required
          value={form.data_inicio}
          onChange={(e) => update("data_inicio", e.target.value)}
          error={fieldErrors.data_inicio}
          disabled={saving}
          data-testid="meta-form-data-inicio"
        />
        <Input
          label="Data de término"
          type="date"
          required
          value={form.data_fim}
          onChange={(e) => update("data_fim", e.target.value)}
          error={fieldErrors.data_fim}
          disabled={saving}
          data-testid="meta-form-data-fim"
        />
      </div>
    </div>
  );
}
