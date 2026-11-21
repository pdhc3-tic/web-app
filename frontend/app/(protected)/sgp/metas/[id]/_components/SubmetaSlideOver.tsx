"use client";

import { useEffect, useState } from "react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { ApiError } from "@/app/lib/api";
import { formatDate } from "@/app/lib/datetime";
import {
  criarSubmeta,
  payloadDaSubmeta,
  proximoNumeroDeSubmeta,
  validarSubmeta,
  type FormSubmeta,
  type MetaDaSubmeta,
  type Submeta,
} from "@/app/lib/submetas";

type Props = {
  open: boolean;
  onClose: () => void;
  meta: MetaDaSubmeta;
  /** As Submetas que a Meta já tem: sugerem o próximo número. */
  existentes: Pick<Submeta, "numero">[];
  onSaved: (submeta: Submeta) => void;
};

function formVazio(meta: MetaDaSubmeta, existentes: Pick<Submeta, "numero">[]): FormSubmeta {
  return {
    numero: proximoNumeroDeSubmeta(meta.numero, existentes),
    titulo: "",
    descricao: "",
    // O período da Meta é o teto: começa preenchido com ele.
    data_inicio: meta.data_inicio,
    data_fim: meta.data_fim,
  };
}

/**
 * Cadastro de Submeta no detalhe da Meta (#431), no padrão do formulário de
 * Ação. O backend confere número, unicidade e período; os erros dele voltam por
 * campo.
 */
export function SubmetaSlideOver({ open, onClose, meta, existentes, onSaved }: Props) {
  const [form, setForm] = useState<FormSubmeta>(() => formVazio(meta, existentes));
  const [salvando, setSalvando] = useState(false);
  const [erros, setErros] = useState<Partial<Record<keyof FormSubmeta, string>>>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);

  // Cada abertura começa do zero, com o próximo número livre.
  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setForm(formVazio(meta, existentes));
    setErros({});
    setErroGeral(null);
    // `existentes` muda de identidade a cada render da página; o que importa é abrir.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, meta]);

  function mudar<K extends keyof FormSubmeta>(campo: K, valor: FormSubmeta[K]) {
    setForm((f) => ({ ...f, [campo]: valor }));
    setErros((e) => {
      if (!(campo in e)) return e;
      const prox = { ...e };
      delete prox[campo];
      return prox;
    });
  }

  async function salvar() {
    if (salvando) return;
    const errosDoCliente = validarSubmeta(form, meta);
    if (Object.keys(errosDoCliente).length > 0) {
      setErros(errosDoCliente);
      setErroGeral("Corrija os campos destacados e tente novamente.");
      return;
    }
    setErros({});
    setErroGeral(null);
    setSalvando(true);
    try {
      onSaved(await criarSubmeta(payloadDaSubmeta(form, meta.id)));
    } catch (e: unknown) {
      if (e instanceof ApiError && e.fieldErrors?.length) {
        const porCampo: Partial<Record<keyof FormSubmeta, string>> = {};
        const outros: string[] = [];
        for (const fe of e.fieldErrors) {
          if (fe.field in form) porCampo[fe.field as keyof FormSubmeta] = fe.message;
          else outros.push(fe.message);
        }
        setErros(porCampo);
        setErroGeral(outros[0] ?? e.message);
        return;
      }
      setErroGeral(e instanceof ApiError ? e.message : "Não foi possível salvar a Submeta. Tente novamente.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={`Nova Submeta da Meta ${meta.numero}`}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={salvando}>
            Cancelar
          </Button>
          <Button onClick={() => void salvar()} loading={salvando} data-testid="submeta-form-submit">
            Salvar
          </Button>
        </div>
      }
    >
      <form
        className="flex flex-col gap-4 px-4 py-4"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void salvar();
        }}
        data-testid="submeta-form"
      >
        {erroGeral && (
          <div role="alert" className="rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text">
            {erroGeral}
          </div>
        )}

        <p className="text-xs text-text-muted">
          As Ações da Meta ficam dentro de uma Submeta: depois de salvar, ela aparece no formulário de Nova ação.
        </p>

        <Input
          label="Número"
          required
          value={form.numero}
          onChange={(e) => mudar("numero", e.target.value)}
          error={erros.numero}
          disabled={salvando}
          autoComplete="off"
          placeholder={`${meta.numero}.1`}
          helperText={`Numeração X.Y, com X igual ao número da Meta (${meta.numero}).`}
          data-testid="submeta-form-numero"
        />
        <Input
          label="Título"
          required
          value={form.titulo}
          onChange={(e) => mudar("titulo", e.target.value)}
          error={erros.titulo}
          disabled={salvando}
          autoComplete="off"
          data-testid="submeta-form-titulo"
        />
        <Textarea
          label="Descrição"
          rows={3}
          value={form.descricao}
          onChange={(e) => mudar("descricao", e.target.value)}
          error={erros.descricao}
          disabled={salvando}
          data-testid="submeta-form-descricao"
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="Data de início"
            type="date"
            required
            value={form.data_inicio}
            onChange={(e) => mudar("data_inicio", e.target.value)}
            error={erros.data_inicio}
            disabled={salvando}
            data-testid="submeta-form-data-inicio"
          />
          <Input
            label="Data de término"
            type="date"
            required
            value={form.data_fim}
            onChange={(e) => mudar("data_fim", e.target.value)}
            error={erros.data_fim}
            disabled={salvando}
            data-testid="submeta-form-data-fim"
          />
        </div>
        <p className="text-xs text-text-muted">
          Dentro do período da Meta: {formatDate(meta.data_inicio)} a {formatDate(meta.data_fim)}.
        </p>
      </form>
    </SlideOver>
  );
}
