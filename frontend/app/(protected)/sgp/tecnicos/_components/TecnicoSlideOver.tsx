"use client";

import { useEffect, useState } from "react";
import { AlertCircleIcon } from "@/app/components/icons";
import { Button } from "@/app/components/ui/Button/Button";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { Input } from "@/app/components/ui/Input/Input";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import {
  createTecnico,
  deactivateTecnico,
  updateTecnico,
  type TecnicoListItem,
  type TecnicoWritePayload,
} from "@/app/lib/tecnicos";

export type TecnicoSlideOverMode = "create" | "edit" | "view";

type Props = {
  open: boolean;
  onClose: () => void;
  mode: TecnicoSlideOverMode;
  tecnico?: TecnicoListItem;
  userOptions: SelectOption[];
  territorioOptions: SelectOption[];
  oscOptions: SelectOption[];
  onSaved: (t: TecnicoListItem) => void;
  onDeactivated: (id: number) => void;
};

type FormState = {
  user: string;
  territorio: string;
  osc: string;
  papel: string;
};

const EMPTY_FORM: FormState = { user: "", territorio: "", osc: "", papel: "" };

function tecnicoToForm(t: TecnicoListItem): FormState {
  return {
    user: String(t.user),
    territorio: t.territorio != null ? String(t.territorio) : "",
    osc: t.osc != null ? String(t.osc) : "",
    papel: t.papel,
  };
}

export function TecnicoSlideOver({
  open,
  onClose,
  mode,
  tecnico,
  userOptions,
  territorioOptions,
  oscOptions,
  onSaved,
  onDeactivated,
}: Props) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [deactivating, setDeactivating] = useState(false);
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setErrors({});
    setGlobalError(null);
    setConfirmDeactivate(false);
    setForm(mode !== "create" && tecnico ? tecnicoToForm(tecnico) : EMPTY_FORM);
  }, [open, mode, tecnico]);

  function patch(p: Partial<FormState>) {
    setForm((prev) => ({ ...prev, ...p }));
    setErrors((prev) => {
      const next = { ...prev };
      for (const k of Object.keys(p)) delete next[k];
      return next;
    });
  }

  function validate(): boolean {
    const errs: Record<string, string> = {};
    if (!form.user) errs.user = "Selecione o usuário.";
    if (!form.papel.trim()) errs.papel = "Informe o papel.";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSave() {
    if (!validate()) return;
    setSaving(true);
    setGlobalError(null);
    const payload: TecnicoWritePayload = {
      user: Number(form.user),
      territorio: form.territorio ? Number(form.territorio) : null,
      osc: form.osc ? Number(form.osc) : null,
      papel: form.papel.trim(),
    };
    try {
      const saved =
        mode === "edit" && tecnico
          ? await updateTecnico(tecnico.id, payload)
          : await createTecnico(payload);
      onSaved(saved);
    } catch (e) {
      if (e instanceof ApiError && e.fieldErrors?.length) {
        const mapped: Record<string, string> = {};
        for (const fe of e.fieldErrors) mapped[fe.field] = fe.message;
        setErrors(mapped);
      } else {
        setGlobalError(
          e instanceof ApiError ? e.message : "Não foi possível salvar.",
        );
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivate() {
    if (!tecnico) return;
    setDeactivating(true);
    setGlobalError(null);
    try {
      await deactivateTecnico(tecnico.id);
      onDeactivated(tecnico.id);
    } catch {
      setGlobalError("Não foi possível desativar o técnico.");
      setDeactivating(false);
    }
  }

  const title =
    mode === "create"
      ? "Novo técnico"
      : mode === "edit"
        ? "Editar técnico"
        : tecnico?.user_nome ?? "Técnico";

  const isReadOnly = mode === "view";

  const footer = isReadOnly ? (
    <div className="flex items-center justify-between gap-2">
      {tecnico?.ativo && (
        <Button
          variant="danger"
          onClick={() => setConfirmDeactivate(true)}
          loading={deactivating}
        >
          Desativar
        </Button>
      )}
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
    <>
      <SlideOver open={open} onClose={onClose} title={title} footer={footer}>
        {globalError && (
          <div className="mx-4 mt-4 flex items-start gap-2 rounded-lg bg-error-bg px-4 py-3">
            <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-error-text" />
            <p className="text-sm text-error-text">{globalError}</p>
          </div>
        )}

        <div className="p-4">
          {isReadOnly && tecnico ? (
            <DefinitionList
              items={[
                { label: "Nome", value: tecnico.user_nome },
                { label: "Papel", value: tecnico.papel },
                { label: "OSC", value: tecnico.osc_nome },
                { label: "Território", value: tecnico.territorio_nome },
                { label: "Situação", value: tecnico.ativo ? "Ativo" : "Inativo" },
              ]}
            />
          ) : (
            <div className="flex flex-col gap-4">
              {mode === "create" && (
                <Select
                  label="Usuário"
                  required
                  options={userOptions}
                  value={form.user}
                  onChange={(v) => patch({ user: v })}
                  error={errors.user}
                  placeholder="Selecione o usuário"
                />
              )}
              <Input
                label="Papel"
                required
                value={form.papel}
                onChange={(e) => patch({ papel: e.target.value })}
                error={errors.papel}
                placeholder="Ex.: ADT, Coordenador..."
              />
              <Select
                label="Território"
                options={territorioOptions}
                value={form.territorio}
                onChange={(v) => patch({ territorio: v })}
                placeholder="Nenhum (acesso global)"
              />
              <Select
                label="OSC"
                options={oscOptions}
                value={form.osc}
                onChange={(v) => patch({ osc: v })}
                placeholder="Nenhuma"
              />
            </div>
          )}
        </div>
      </SlideOver>

      <SlideOver
        open={confirmDeactivate}
        onClose={() => setConfirmDeactivate(false)}
        title="Desativar técnico?"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => setConfirmDeactivate(false)}
              disabled={deactivating}
            >
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={handleDeactivate}
              loading={deactivating}
            >
              Desativar
            </Button>
          </div>
        }
      >
        <div className="flex items-start gap-3 p-4">
          <AlertCircleIcon className="mt-0.5 h-5 w-5 shrink-0 text-error-text" />
          <p className="text-sm leading-relaxed text-text">
            O técnico será desativado, mas todas as atividades históricas
            vinculadas a ele são preservadas.
          </p>
        </div>
      </SlideOver>
    </>
  );
}
