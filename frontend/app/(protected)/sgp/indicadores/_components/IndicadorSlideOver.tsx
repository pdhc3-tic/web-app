"use client";

import { useEffect, useId, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import {
  atualizarIndicador,
  CATEGORIA_LABEL,
  CODIGO_CONFIRMAR_RECALCULO,
  criarIndicador,
  DESAGREGACAO_LABEL,
  FORMA_APURACAO_LABEL,
  opcoes,
  UNIDADE_MEDIDA_LABEL,
  type CategoriaIndicador,
  type Desagregacao,
  type FormaApuracao,
  type Indicador,
  type IndicadorPayload,
  type UnidadeMedida,
} from "@/app/lib/indicadores";
import { OdsPicker } from "../../metas/_components/OdsPicker";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Null: novo indicador. */
  indicador: Indicador | null;
  onSaved: (salvo: Indicador, novo: boolean) => void;
};

type FormState = {
  codigo: string;
  nome: string;
  unidade_medida: UnidadeMedida | "";
  forma_apuracao: FormaApuracao | "";
  categoria: CategoriaIndicador | "";
  ods_ids: number[];
  desagregacoes: Desagregacao[];
  ativo: boolean;
};

const VAZIO: FormState = {
  codigo: "",
  nome: "",
  unidade_medida: "",
  forma_apuracao: "",
  categoria: "",
  ods_ids: [],
  desagregacoes: [],
  ativo: true,
};

function doIndicador(i: Indicador): FormState {
  return {
    codigo: i.codigo,
    nome: i.nome,
    unidade_medida: i.unidade_medida,
    forma_apuracao: i.forma_apuracao,
    categoria: i.categoria ?? "",
    ods_ids: i.ods_ids ?? [],
    desagregacoes: i.desagregacoes ?? [],
    ativo: i.ativo,
  };
}

/** O que dá para conferir sem o servidor; código único e ODS válidos voltam como erro de campo. */
function validar(f: FormState): Record<string, string> {
  const erros: Record<string, string> = {};
  if (!f.codigo.trim()) erros.codigo = "Informe o código do indicador.";
  if (!f.nome.trim()) erros.nome = "Informe o nome do indicador.";
  if (!f.unidade_medida) erros.unidade_medida = "Escolha a unidade de medida.";
  if (!f.forma_apuracao) erros.forma_apuracao = "Escolha a forma de apuração.";
  return erros;
}

const DESAGREGACOES = opcoes(DESAGREGACAO_LABEL);

/**
 * Novo indicador e edição (SGP §5.4, #453), no formato do painel de Meta.
 *
 * Trocar a forma de apuração de um indicador com Ações recalcula a quantidade
 * já apurada delas: o backend responde 409 `confirmacao_necessaria` com quantas
 * são, o painel mostra o aviso, e só o "Confirmar e recalcular" reenvia com
 * `confirmar_recalculo`.
 */
export function IndicadorSlideOver({ open, onClose, indicador, onSaved }: Props) {
  const [form, setForm] = useState<FormState>(VAZIO);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  /** Mensagem do 409 de recálculo; presente enquanto a confirmação está aberta. */
  const [recalculo, setRecalculo] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const idDesagregacao = useId();

  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setForm(indicador ? doIndicador(indicador) : VAZIO);
    setErros({});
    setErroGeral(null);
    setRecalculo(null);
  }, [open, indicador]);

  function mudar<K extends keyof FormState>(campo: K, valor: FormState[K]) {
    setForm((f) => ({ ...f, [campo]: valor }));
    setErros((e) => {
      if (!(campo in e)) return e;
      const prox = { ...e };
      delete prox[campo];
      return prox;
    });
    if (campo === "forma_apuracao") setRecalculo(null);
  }

  function alternarDesagregacao(valor: Desagregacao) {
    mudar(
      "desagregacoes",
      form.desagregacoes.includes(valor)
        ? form.desagregacoes.filter((d) => d !== valor)
        : DESAGREGACOES.map((d) => d.value).filter((d) => d === valor || form.desagregacoes.includes(d)),
    );
  }

  async function salvar(confirmarRecalculo = false) {
    if (salvando) return;
    const e = validar(form);
    if (Object.keys(e).length > 0) {
      setErros(e);
      setErroGeral("Corrija os campos destacados e tente novamente.");
      return;
    }
    const payload: IndicadorPayload = {
      codigo: form.codigo.trim(),
      nome: form.nome.trim(),
      unidade_medida: form.unidade_medida as UnidadeMedida,
      forma_apuracao: form.forma_apuracao as FormaApuracao,
      categoria: form.categoria,
      ods_ids: form.ods_ids,
      desagregacoes: form.desagregacoes,
      ativo: form.ativo,
    };

    setSalvando(true);
    setErros({});
    setErroGeral(null);
    try {
      const salvo = indicador
        ? await atualizarIndicador(indicador.id, payload, confirmarRecalculo)
        : await criarIndicador(payload);
      setRecalculo(null);
      onSaved(salvo, indicador === null);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.code === CODIGO_CONFIRMAR_RECALCULO) {
        setRecalculo(err.message);
        return;
      }
      if (err instanceof ApiError && err.fieldErrors?.length) {
        setErros(Object.fromEntries(err.fieldErrors.map((fe) => [fe.field, fe.message])));
      }
      setErroGeral(err instanceof ApiError ? err.message : "Não foi possível salvar o indicador. Tente novamente.");
    } finally {
      setSalvando(false);
    }
  }

  const rodape = recalculo ? (
    <div className="flex items-center justify-end gap-2">
      <Button variant="ghost" onClick={() => setRecalculo(null)} disabled={salvando}>
        Voltar
      </Button>
      <Button onClick={() => salvar(true)} loading={salvando} data-testid="indicador-confirmar-recalculo">
        Confirmar e recalcular
      </Button>
    </div>
  ) : (
    <div className="flex items-center justify-end gap-2">
      <Button variant="ghost" onClick={onClose} disabled={salvando}>
        Cancelar
      </Button>
      <Button onClick={() => salvar()} loading={salvando} data-testid="indicador-form-salvar">
        Salvar
      </Button>
    </div>
  );

  return (
    <SlideOver
      open={open}
      onClose={salvando ? () => {} : onClose}
      title={indicador ? `Editar indicador ${indicador.codigo}` : "Novo indicador"}
      footer={rodape}
      width="wide"
    >
      <div className="flex flex-col gap-4 px-4 py-4" data-testid="indicador-form">
        {recalculo && (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-md border border-warning-text bg-warning-bg px-3 py-3 text-sm text-warning-text"
            data-testid="indicador-recalculo"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <div className="flex flex-col gap-1">
              <p className="font-medium">Esta troca recalcula as Ações que usam o indicador.</p>
              <p>{recalculo.replace(/ Reenvie com confirmar_recalculo=true para confirmar\.?$/, "")}</p>
              <p>
                A quantidade realizada delas passa a ser apurada por &ldquo;
                {FORMA_APURACAO_LABEL[form.forma_apuracao as FormaApuracao] ?? form.forma_apuracao}&rdquo;.
              </p>
            </div>
          </div>
        )}

        {erroGeral && (
          <div
            role="alert"
            className="rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text"
            data-testid="indicador-form-erro"
          >
            {erroGeral}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[12rem_1fr]">
          <Input
            label="Código"
            required
            maxLength={20}
            value={form.codigo}
            onChange={(e) => mudar("codigo", e.target.value)}
            error={erros.codigo}
            disabled={salvando}
            helperText="Curto e estável, ex.: IND-OFI."
            autoComplete="off"
            data-testid="indicador-form-codigo"
          />
          <Input
            label="Nome"
            required
            maxLength={255}
            value={form.nome}
            onChange={(e) => mudar("nome", e.target.value)}
            error={erros.nome}
            disabled={salvando}
            autoComplete="off"
            data-testid="indicador-form-nome"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select
            id="indicador-form-unidade"
            label="Unidade de medida"
            required
            options={opcoes(UNIDADE_MEDIDA_LABEL)}
            value={form.unidade_medida}
            onChange={(v) => mudar("unidade_medida", v as UnidadeMedida)}
            placeholder="Selecione…"
            error={erros.unidade_medida}
            disabled={salvando}
          />
          <Select
            id="indicador-form-categoria"
            label="Categoria"
            options={[{ value: "", label: "Sem categoria" }, ...opcoes(CATEGORIA_LABEL)]}
            value={form.categoria}
            onChange={(v) => mudar("categoria", v as CategoriaIndicador | "")}
            placeholder="Sem categoria"
            error={erros.categoria}
            disabled={salvando}
          />
        </div>

        <Select
          id="indicador-form-forma"
          label="Forma de apuração"
          required
          options={opcoes(FORMA_APURACAO_LABEL)}
          value={form.forma_apuracao}
          onChange={(v) => mudar("forma_apuracao", v as FormaApuracao)}
          placeholder="Selecione…"
          helperText={
            indicador
              ? "Trocar a forma de um indicador já usado por Ações recalcula a quantidade realizada delas."
              : "Como a quantidade realizada das Ações é apurada."
          }
          error={erros.forma_apuracao}
          disabled={salvando}
        />

        <OdsPicker
          value={form.ods_ids}
          onChange={(v) => mudar("ods_ids", v)}
          error={erros.ods_ids}
          disabled={salvando}
          descricao="Objetivos de Desenvolvimento Sustentável a que o indicador contribui."
          testId="indicador-form-ods"
        />

        <fieldset className="flex flex-col gap-1" aria-describedby={erros.desagregacoes ? `${idDesagregacao}-erro` : undefined}>
          <legend className="text-label font-medium leading-[1.2] text-text">Desagregação exigida</legend>
          <p className="text-2xs text-text-muted">Recortes que o relatório do indicador precisa produzir.</p>
          <div className="mt-1 flex flex-wrap gap-x-5 gap-y-2" data-testid="indicador-form-desagregacoes">
            {DESAGREGACOES.map((d) => (
              <label key={d.value} className="flex items-center gap-2 text-sm text-text">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-[var(--color-primary)]"
                  checked={form.desagregacoes.includes(d.value)}
                  onChange={() => alternarDesagregacao(d.value)}
                  disabled={salvando}
                />
                {d.label}
              </label>
            ))}
          </div>
          {erros.desagregacoes && (
            <span id={`${idDesagregacao}-erro`} role="alert" className="text-2xs text-error-text">
              {erros.desagregacoes}
            </span>
          )}
        </fieldset>

        <label className="flex items-start gap-2 text-sm text-text">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 accent-[var(--color-primary)]"
            checked={form.ativo}
            onChange={(e) => mudar("ativo", e.target.checked)}
            disabled={salvando}
            data-testid="indicador-form-ativo"
          />
          <span>
            Ativo
            <span className="block text-2xs text-text-muted">
              Inativo não pode ser vinculado a novas Ações, mas o histórico das que já o usam fica.
            </span>
          </span>
        </label>
      </div>
    </SlideOver>
  );
}
