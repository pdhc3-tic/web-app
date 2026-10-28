"use client";

import { useEffect, useState } from "react";
import { AlertCircleIcon } from "@/app/components/icons";
import { Button } from "@/app/components/ui/Button/Button";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { Input } from "@/app/components/ui/Input/Input";
import {
  SearchSelect,
  type SearchSelectOption,
} from "@/app/components/ui/SearchSelect/SearchSelect";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import { qk } from "@/app/lib/queryKeys";
import {
  createTecnico,
  deactivateTecnico,
  searchUsuariosElegiveis,
  updateTecnico,
  type TecnicoListItem,
  type TecnicoWritePayload,
  type UsuarioElegivel,
} from "@/app/lib/tecnicos";

export type TecnicoSlideOverMode = "create" | "edit" | "view";

type Props = {
  open: boolean;
  onClose: () => void;
  mode: TecnicoSlideOverMode;
  tecnico?: TecnicoListItem;
  territorioOptions: SelectOption[];
  oscOptions: SelectOption[];
  onSaved: (t: TecnicoListItem) => void;
  onDeactivated: (id: number) => void;
};

type FormState = {
  user: UsuarioElegivel | null;
  territorio: string;
  osc: string;
  papel: string;
};

const EMPTY_FORM: FormState = {
  user: null,
  territorio: "",
  osc: "",
  papel: "",
};

function usuarioParaOpcao(
  u: UsuarioElegivel,
): SearchSelectOption<UsuarioElegivel> {
  return {
    value: String(u.id),
    label: u.nome_completo,
    description: u.email,
    item: u,
  };
}

function tecnicoToForm(t: TecnicoListItem): FormState {
  // No modo edit o user é read-only (o backend não deixa trocá-lo), então
  // guardamos só o id/nome que a listagem já traz. A busca de elegíveis não
  // seria capaz de devolvê-lo (ele já é técnico).
  return {
    user: {
      id: t.user,
      nome_completo: t.user_nome,
      email: "",
    },
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

  // Reset a cada abertura, mesmo padrão do MapeamentoDialog: o painel limpa os
  // controles no `open` de false→true, sem desmontar a cada ciclo da animação.
  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
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

  /**
   * O backend devolve `{code, message}` por `ErroComCodigo` (A2 da #302). Daí
   * mapeamos pelo code, não pela regex do texto. Codes conhecidos:
   * - `tecnico_duplicado`: usuário já cadastrado;
   * - `conflito_vinculo`: OSC não atua no território;
   * - `tecnico_ja_inativo`: na desativação de um técnico já inativo.
   */
  function mensagemDoCode(e: ApiError): string {
    switch (e.code) {
      case "tecnico_duplicado":
        return "Este usuário já está cadastrado como técnico.";
      case "conflito_vinculo":
        return "A OSC selecionada não atua neste território.";
      case "tecnico_ja_inativo":
        return "Este técnico já está inativo.";
      default:
        return e.message || "Não foi possível concluir a operação.";
    }
  }

  async function handleSave() {
    if (!validate()) return;
    setSaving(true);
    setGlobalError(null);
    const payload: TecnicoWritePayload = {
      user: form.user!.id,
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
      if (e instanceof ApiError) {
        if (e.status === 403) {
          setGlobalError("Você não tem permissão para esta ação.");
        } else if (e.fieldErrors?.length) {
          const mapped: Record<string, string> = {};
          for (const fe of e.fieldErrors) mapped[fe.field] = fe.message;
          setErrors(mapped);
        } else {
          setGlobalError(mensagemDoCode(e));
        }
      } else {
        setGlobalError("Não foi possível salvar.");
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
      setConfirmDeactivate(false);
      onDeactivated(tecnico.id);
    } catch (e) {
      // O erro aparece no painel de edição, que fica coberto pela confirmação.
      setConfirmDeactivate(false);
      if (e instanceof ApiError && e.status === 403) {
        setGlobalError("Você não tem permissão para esta ação.");
      } else if (e instanceof ApiError) {
        setGlobalError(mensagemDoCode(e));
      } else {
        setGlobalError("Não foi possível desativar o técnico.");
      }
    } finally {
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
    <div className="flex justify-end">
      <Button variant="secondary" onClick={onClose}>
        Fechar
      </Button>
    </div>
  ) : (
    <div className="flex items-center justify-between gap-2">
      {mode === "edit" && tecnico?.ativo && (
        <Button
          variant="danger"
          onClick={() => setConfirmDeactivate(true)}
          loading={deactivating}
        >
          Desativar
        </Button>
      )}
      <div className="ml-auto flex items-center gap-2">
        <Button variant="ghost" onClick={onClose} disabled={saving}>
          Cancelar
        </Button>
        <Button onClick={handleSave} loading={saving}>
          Salvar
        </Button>
      </div>
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
                <SearchSelect<UsuarioElegivel>
                  label="Usuário"
                  required
                  value={form.user ? usuarioParaOpcao(form.user) : null}
                  onChange={(opcao) => patch({ user: opcao?.item ?? null })}
                  search={async (texto, signal) =>
                    (await searchUsuariosElegiveis(texto, signal)).map(
                      usuarioParaOpcao,
                    )
                  }
                  queryKey={(texto) => qk.usuariosElegiveisTecnico(texto)}
                  placeholder="Buscar por nome do usuário…"
                  emptyText="Nenhum usuário elegível com esse nome."
                  error={errors.user}
                  data-testid="tecnico-usuario"
                />
              )}
              <Input
                id="tecnico-papel"
                label="Papel"
                required
                value={form.papel}
                onChange={(e) => patch({ papel: e.target.value })}
                error={errors.papel}
                placeholder="Ex.: ADT, Coordenador..."
              />
              <Select
                id="tecnico-territorio"
                label="Território"
                options={territorioOptions}
                value={form.territorio}
                onChange={(v) => patch({ territorio: v })}
                placeholder="Nenhum (acesso global)"
              />
              <Select
                id="tecnico-osc"
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
