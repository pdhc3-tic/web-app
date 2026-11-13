"use client";

import { useState, type FormEvent } from "react";
import { AlertTriangle, Plus, Trash2 } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { ApiError } from "@/app/lib/api";
import type { Perfil } from "@/app/lib/auth/types";
import {
  OBJETO_DO_PERFIL,
  OBJETO_TIPO_LABEL,
  criarUsuario,
  opcoesDePerfil,
  validarNovoUsuario,
  type ErrosNovoUsuario,
  type LinhaOperacional,
  type LinhaPrincipal,
  type NovoUsuario,
  type UserListItem,
} from "@/app/lib/users";

type Props = {
  perfis: Perfil[];
  territoryOptions: SelectOption[];
  onCriado: (usuario: UserListItem) => void;
  onCancelar: () => void;
};

const VAZIO: NovoUsuario = {
  nome: "",
  email: "",
  senha: "",
  principais: [{ perfil: "", territorio: "" }],
  operacionais: [],
};

const TODOS_OS_TERRITORIOS: SelectOption = { value: "", label: "Todos os territórios" };

/**
 * Cadastro de usuário (#405, CORE-RF08/RF09).
 *
 * Os perfis ficam em duas seções, porque a abrangência de cada categoria é
 * outra: o **principal** vale num território (ou em todos) e o **operacional**
 * vale num objeto (evento, edital ou candidatura), cujo tipo vem do próprio
 * perfil. O seletor de objeto só existe na seção dos operacionais.
 *
 * O SGE e o SGS ainda não têm os cadastros desses objetos, então o objeto é
 * informado pelo número, como o backend guarda (`objeto_id`, sem FK). A busca
 * desses objetos é a pendência 9 de `docs/pendencias-backend-sprint-12b.md`.
 */
export function NovoUsuarioForm({ perfis, territoryOptions, onCriado, onCancelar }: Props) {
  const [form, setForm] = useState<NovoUsuario>(VAZIO);
  const [erros, setErros] = useState<ErrosNovoUsuario>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const principaisOptions = opcoesDePerfil(perfis, "principal");
  const operacionaisOptions = opcoesDePerfil(perfis, "operacional");
  const territorios = [TODOS_OS_TERRITORIOS, ...territoryOptions];

  function mudarPrincipal(i: number, patch: Partial<LinhaPrincipal>) {
    setForm((f) => ({ ...f, principais: f.principais.map((l, j) => (j === i ? { ...l, ...patch } : l)) }));
    setErros((e) => ({ ...e, principais: undefined }));
  }

  function mudarOperacional(i: number, patch: Partial<LinhaOperacional>) {
    setForm((f) => ({ ...f, operacionais: f.operacionais.map((l, j) => (j === i ? { ...l, ...patch } : l)) }));
    setErros((e) => ({ ...e, operacionais: undefined }));
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    if (enviando) return;
    setErroGeral(null);
    const e = validarNovoUsuario(form, perfis);
    setErros(e);
    if (Object.keys(e).length > 0) return;

    setEnviando(true);
    try {
      onCriado(await criarUsuario(form, perfis));
    } catch (err) {
      if (err instanceof ApiError) {
        const porCampo: ErrosNovoUsuario = {};
        for (const fe of err.fieldErrors ?? []) {
          if (fe.field === "email") porCampo.email = fe.message;
          else if (fe.field === "nome_completo") porCampo.nome = fe.message;
        }
        setErros(porCampo);
        // Erros de `perfis_input` vêm sem linha: ficam no aviso geral.
        if (Object.keys(porCampo).length === 0) {
          setErroGeral(err.fieldErrors?.[0]?.message ?? err.message);
        }
      } else {
        setErroGeral("Não foi possível criar o usuário. Tente novamente.");
      }
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-6" data-testid="novo-usuario-form">
      <div className="flex flex-col gap-4">
        <Input
          id="usuario-nome"
          label="Nome completo"
          required
          value={form.nome}
          onChange={(e) => {
            setForm((f) => ({ ...f, nome: e.target.value }));
            setErros((x) => ({ ...x, nome: undefined }));
          }}
          error={erros.nome}
        />
        <Input
          id="usuario-email"
          label="E-mail"
          type="email"
          required
          value={form.email}
          onChange={(e) => {
            setForm((f) => ({ ...f, email: e.target.value }));
            setErros((x) => ({ ...x, email: undefined }));
          }}
          error={erros.email}
        />
        <Input
          id="usuario-senha"
          label="Senha inicial"
          type="password"
          autoComplete="new-password"
          value={form.senha}
          onChange={(e) => setForm((f) => ({ ...f, senha: e.target.value }))}
          helperText="Opcional. Sem senha, a pessoa define a sua em “Esqueci minha senha”."
        />
      </div>

      {/* ── Perfis principais ─────────────────────────────────────────── */}
      <fieldset className="flex flex-col gap-3" data-testid="perfis-principais">
        <legend className="text-sm font-semibold text-text">Perfis principais</legend>
        <p className="text-xs text-text-muted">
          Definem o que a pessoa faz no sistema. Cada um vale num território, ou em todos.
        </p>
        {form.principais.map((linha, i) => (
          <div
            key={i}
            className="flex flex-wrap items-end gap-2 rounded-md border border-border p-3"
            data-testid={`perfil-principal-${i}`}
          >
            <div className="min-w-40 flex-1">
              <Select
                id={`perfil-principal-${i}-perfil`}
                label="Perfil"
                required
                options={principaisOptions}
                value={linha.perfil}
                onChange={(v) => mudarPrincipal(i, { perfil: v })}
              />
            </div>
            <div className="min-w-40 flex-1">
              <Select
                id={`perfil-principal-${i}-territorio`}
                label="Território"
                options={territorios}
                value={linha.territorio}
                onChange={(v) => mudarPrincipal(i, { territorio: v })}
                placeholder="Todos os territórios"
              />
            </div>
            {form.principais.length > 1 && (
              <button
                type="button"
                aria-label="Remover perfil principal"
                onClick={() => setForm((f) => ({ ...f, principais: f.principais.filter((_, j) => j !== i) }))}
                className="flex h-9 w-9 items-center justify-center rounded-md text-text-muted hover:bg-error-bg hover:text-error-text"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        ))}
        {erros.principais && (
          <p role="alert" className="text-sm text-error-text" data-testid="perfis-principais-erro">
            {erros.principais}
          </p>
        )}
        <div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() =>
              setForm((f) => ({ ...f, principais: [...f.principais, { perfil: "", territorio: "" }] }))
            }
            data-testid="perfil-principal-adicionar"
          >
            Adicionar perfil principal
          </Button>
        </div>
      </fieldset>

      {/* ── Perfis operacionais ───────────────────────────────────────── */}
      <fieldset className="flex flex-col gap-3" data-testid="perfis-operacionais">
        <legend className="text-sm font-semibold text-text">Perfis operacionais</legend>
        <p className="text-xs text-text-muted">
          Opcionais. Valem só num objeto (um evento, um edital ou uma candidatura) e acompanham um perfil
          principal.
        </p>
        {form.operacionais.map((linha, i) => {
          const perfil = perfis.find((p) => String(p.id) === linha.perfil);
          const tipo = perfil ? OBJETO_DO_PERFIL[perfil.slug] : undefined;
          const erro = erros.operacionais?.[i];
          return (
            <div key={i} className="flex flex-col gap-2 rounded-md border border-border p-3" data-testid={`perfil-operacional-${i}`}>
              <div className="flex flex-wrap items-end gap-2">
                <div className="min-w-40 flex-1">
                  <Select
                    id={`perfil-operacional-${i}-perfil`}
                    label="Perfil"
                    required
                    options={operacionaisOptions}
                    value={linha.perfil}
                    onChange={(v) => mudarOperacional(i, { perfil: v })}
                  />
                </div>
                {/* O objeto de abrangência: o tipo vem do perfil escolhido. */}
                <div className="min-w-40 flex-1" data-testid={`perfil-operacional-${i}-objeto`}>
                  <Input
                    id={`perfil-operacional-${i}-objeto-id`}
                    label={tipo ? `${OBJETO_TIPO_LABEL[tipo]} (número)` : "Objeto de abrangência (número)"}
                    inputMode="numeric"
                    required
                    disabled={!linha.perfil}
                    value={linha.objetoId}
                    onChange={(e) => mudarOperacional(i, { objetoId: e.target.value })}
                    placeholder={linha.perfil ? "Ex.: 12" : "Escolha o perfil"}
                  />
                </div>
                <button
                  type="button"
                  aria-label="Remover perfil operacional"
                  onClick={() => {
                    setForm((f) => ({ ...f, operacionais: f.operacionais.filter((_, j) => j !== i) }));
                    setErros((e) => ({ ...e, operacionais: undefined }));
                  }}
                  className="flex h-9 w-9 items-center justify-center rounded-md text-text-muted hover:bg-error-bg hover:text-error-text"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              {erro && (
                <p role="alert" className="text-sm text-error-text" data-testid={`perfil-operacional-${i}-erro`}>
                  {erro}
                </p>
              )}
            </div>
          );
        })}
        <div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            leftIcon={<Plus className="h-4 w-4" />}
            disabled={operacionaisOptions.length === 0}
            onClick={() =>
              setForm((f) => ({ ...f, operacionais: [...f.operacionais, { perfil: "", objetoId: "" }] }))
            }
            data-testid="perfil-operacional-adicionar"
          >
            Adicionar perfil operacional
          </Button>
        </div>
      </fieldset>

      {erroGeral && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
          data-testid="novo-usuario-erro"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {erroGeral}
        </p>
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onCancelar}>
          Cancelar
        </Button>
        <Button type="submit" loading={enviando} data-testid="novo-usuario-salvar">
          Criar usuário
        </Button>
      </div>
    </form>
  );
}
