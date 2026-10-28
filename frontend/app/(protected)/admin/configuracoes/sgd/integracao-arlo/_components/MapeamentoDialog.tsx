"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircleIcon } from "@/app/components/icons";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import {
  createArloMapping,
  deleteArloMapping,
  mensagemErroArloMapping,
  updateArloMapping,
  type ArloFieldMapping,
  type CampoArlo,
  type DirecaoArlo,
  type FormatoArlo,
} from "@/app/lib/arloMapping";

export type ModoDialogo = "criar" | "editar";

type Props = {
  open: boolean;
  onClose: () => void;
  modo: ModoDialogo;
  direcao: DirecaoArlo;
  linha?: ArloFieldMapping;
  camposDaDirecao: CampoArlo[];
  camposMapeados: Set<string>;
  onSalvo: () => void;
};

type FormState = {
  campo_sgd: string;
  coluna_arlo: string;
  formato: FormatoArlo;
  ativo: boolean;
};

const EMPTY: FormState = {
  campo_sgd: "",
  coluna_arlo: "",
  formato: "texto",
  ativo: true,
};

export function MapeamentoDialog({
  open,
  onClose,
  modo,
  direcao,
  linha,
  camposDaDirecao,
  camposMapeados,
  onSalvo,
}: Props) {
  const { showToast } = useToast();

  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmarRemover, setConfirmarRemover] = useState(false);

  // Reset do form a cada abertura. Mesma supressão de lint das outras telas
  // (ex.: AcessosSCAPage, TecnicoSlideOver): o painel precisa limpar os
  // controles no `open` de false→true, sem desmontar a cada ciclo da animação.
  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setErrors({});
    setGlobalError(null);
    setConfirmarRemover(false);
    if (modo === "editar" && linha) {
      setForm({
        campo_sgd: linha.campo_sgd,
        coluna_arlo: linha.coluna_arlo,
        formato: linha.formato,
        ativo: linha.ativo,
      });
    } else {
      setForm(EMPTY);
    }
  }, [open, modo, linha]);

  // Para criar: só campos ainda não mapeados nessa direção aparecem no select.
  // Para editar: o próprio campo da linha fica fixo (o backend trata direção e
  // campo como read-only no PATCH).
  const camposDisponiveis: SelectOption[] = useMemo(() => {
    if (modo === "editar" && linha) {
      const meta = camposDaDirecao.find((c) => c.campo === linha.campo_sgd);
      return [
        {
          value: linha.campo_sgd,
          label: meta?.label ?? linha.campo_sgd,
        },
      ];
    }
    return camposDaDirecao
      .filter((c) => !camposMapeados.has(c.campo))
      .map((c) => ({ value: c.campo, label: c.label }));
  }, [modo, linha, camposDaDirecao, camposMapeados]);

  const metaDoCampoAtual = camposDaDirecao.find(
    (c) => c.campo === form.campo_sgd,
  );
  const formatosDoCampo: SelectOption[] = (
    metaDoCampoAtual?.formatos ?? [{ value: "texto", label: "Texto" }]
  ).map((f) => ({ value: f.value, label: f.label }));

  // Trocar o campo pode invalidar o formato: num campo monetário "data" não
  // vale. O default é o primeiro aceito; o backend decide o formato padrão por
  // campo (TEXTO/DATA/MOEDA conforme o tipo), e o front espelha o permitido.
  function trocarCampo(campo: string) {
    const meta = camposDaDirecao.find((c) => c.campo === campo);
    const permitidos = (meta?.formatos ?? []).map((f) => f.value);
    const formatoAtualOk = permitidos.includes(form.formato);
    setForm((prev) => ({
      ...prev,
      campo_sgd: campo,
      formato: formatoAtualOk ? prev.formato : permitidos[0] ?? "texto",
    }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next.campo_sgd;
      delete next.formato;
      return next;
    });
  }

  function validar(): boolean {
    const errs: Record<string, string> = {};
    if (!form.campo_sgd) errs.campo_sgd = "Selecione o campo do SGD.";
    if (!form.coluna_arlo.trim()) errs.coluna_arlo = "Informe o nome da coluna.";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSalvar() {
    if (!validar()) return;
    setSaving(true);
    setGlobalError(null);
    try {
      if (modo === "editar" && linha) {
        await updateArloMapping(linha.id, {
          coluna_arlo: form.coluna_arlo.trim(),
          formato: form.formato,
          ativo: form.ativo,
        });
        showToast("Mapeamento atualizado.", "success");
      } else {
        await createArloMapping({
          direcao,
          campo_sgd: form.campo_sgd,
          coluna_arlo: form.coluna_arlo.trim(),
          formato: form.formato,
          ativo: form.ativo,
        });
        showToast("Coluna adicionada.", "success");
      }
      onSalvo();
    } catch (e) {
      if (e instanceof ApiError && e.fieldErrors?.length) {
        const mapeados: Record<string, string> = {};
        for (const fe of e.fieldErrors) mapeados[fe.field] = fe.message;
        setErrors(mapeados);
      } else if (e instanceof ApiError) {
        setGlobalError(mensagemErroArloMapping(e));
      } else {
        setGlobalError("Não foi possível salvar.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleRemover() {
    if (!linha) return;
    setDeleting(true);
    setGlobalError(null);
    try {
      await deleteArloMapping(linha.id);
      showToast("Coluna removida.", "success");
      setConfirmarRemover(false);
      onSalvo();
    } catch (e) {
      // O erro aparece no painel de edição, que fica coberto pela confirmação.
      setConfirmarRemover(false);
      setGlobalError(
        e instanceof ApiError
          ? mensagemErroArloMapping(e)
          : "Não foi possível remover.",
      );
    } finally {
      setDeleting(false);
    }
  }

  const title = modo === "criar" ? "Nova coluna" : "Editar coluna";

  const footer = (
    <div className="flex items-center justify-between gap-2">
      {modo === "editar" && (
        <Button
          variant="danger"
          onClick={() => setConfirmarRemover(true)}
          loading={deleting}
          disabled={saving}
          data-testid="arlo-remover"
        >
          Remover
        </Button>
      )}
      <div className="ml-auto flex items-center gap-2">
        <Button variant="ghost" onClick={onClose} disabled={saving || deleting}>
          Cancelar
        </Button>
        <Button
          onClick={handleSalvar}
          loading={saving}
          disabled={deleting}
          data-testid="arlo-salvar"
        >
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

        <div className="flex flex-col gap-4 p-4">
          <Select
            id="arlo-campo"
            label="Campo do SGD"
            required
            options={camposDisponiveis}
            value={form.campo_sgd}
            onChange={trocarCampo}
            disabled={modo === "editar"}
            error={errors.campo_sgd}
            placeholder={
              camposDisponiveis.length === 0
                ? "Todos os campos já estão mapeados"
                : "Selecione o campo"
            }
          />
          {metaDoCampoAtual?.obrigatorio && (
            <p className="-mt-2 text-xs text-text-muted">
              Campo obrigatório na operação. Precisa continuar ativo.
            </p>
          )}

          <Input
            id="arlo-coluna"
            label="Coluna no Arlo"
            required
            value={form.coluna_arlo}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, coluna_arlo: e.target.value }))
            }
            error={errors.coluna_arlo}
            placeholder="Ex.: Valor Autorizado"
          />

          <Select
            id="arlo-formato"
            label="Formato"
            required
            options={formatosDoCampo}
            value={form.formato}
            onChange={(v) =>
              setForm((prev) => ({ ...prev, formato: v as FormatoArlo }))
            }
            disabled={formatosDoCampo.length <= 1}
            error={errors.formato}
          />

          <label className="flex items-center gap-2 text-sm text-text">
            <input
              type="checkbox"
              checked={form.ativo}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, ativo: e.target.checked }))
              }
              className="h-4 w-4 rounded border-border text-primary focus-visible:ring-2 focus-visible:ring-primary"
            />
            Coluna ativa
          </label>
          <p className="-mt-3 text-xs text-text-muted">
            Colunas inativas não entram na próxima exportação ou importação, mas
            ficam preservadas aqui para serem reativadas depois.
          </p>
        </div>
      </SlideOver>

      <SlideOver
        open={confirmarRemover}
        onClose={() => setConfirmarRemover(false)}
        title="Remover esta coluna?"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => setConfirmarRemover(false)}
              disabled={deleting}
            >
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={handleRemover}
              loading={deleting}
              data-testid="arlo-confirmar-remocao"
            >
              Remover
            </Button>
          </div>
        }
      >
        <div className="flex items-start gap-3 p-4">
          <AlertCircleIcon className="mt-0.5 h-5 w-5 shrink-0 text-error-text" />
          <p className="text-sm leading-relaxed text-text">
            A coluna não vai mais aparecer nas operações. Se precisar dela de
            novo, cadastre uma nova com o mesmo campo.
          </p>
        </div>
      </SlideOver>
    </>
  );
}
