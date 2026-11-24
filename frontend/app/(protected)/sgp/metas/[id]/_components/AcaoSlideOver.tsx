"use client";

import { useEffect, useState } from "react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { ApiError } from "@/app/lib/api";
import {
  NUMERO_ACAO_RE,
  createAcao,
  formatQtd,
  listIndicadores,
  listSubmetasDaMeta,
  proximoNumeroDeAcao,
  updateAcao,
  type Acao,
  type AcaoWritePayload,
  type IndicadorOption,
  type SubmetaOption,
} from "@/app/lib/acoes";
import { decOrNull, formatCurrencyBRL, formatMoneyInput, moneyOrNull } from "@/app/lib/format";
import type { Rubrica } from "@/app/lib/tiposSolicitacao";

// ─── Tipos ───────────────────────────────────────────────────────────────────

export type AcaoSlideOverMode = "create" | "edit";

type Props = {
  open: boolean;
  onClose: () => void;
  mode: AcaoSlideOverMode;
  /** Meta à qual a Ação pertence — obrigatória no payload. */
  metaId: number;
  /** Em "edit", a Ação sendo editada. */
  acao?: Acao;
  /** As Ações que a Meta já tem: sugerem o próximo número da Submeta (#452). */
  existentes: Pick<Acao, "id" | "numero">[];
  /** Catálogo de rubricas, com as inativas; `undefined` enquanto carrega. */
  rubricas: Rubrica[] | undefined;
  /** A leitura do catálogo de rubricas falhou. */
  rubricasFalhou?: boolean;
  onSaved: (acao: Acao, mode: AcaoSlideOverMode) => void;
  /**
   * Leva ao cadastro de Submeta (#431). Sem Submeta na Meta, a Ação não tem
   * como ser salva, e o formulário oferece este caminho em vez de travar.
   */
  onPedirSubmeta?: () => void;
};

type FormState = {
  numero: string;
  descricao: string;
  /** String porque vem do <Select>; convertido em formToPayload. */
  submeta: string;
  /** String porque vem do <Select>; convertido em formToPayload. */
  indicador: string;
  quantidade_planejada: string;
  /** Mascarado como moeda ("R$ 3.500,00"); convertido em formToPayload. */
  valor_unitario: string;
  data_inicio: string;
  data_fim: string;
  /** Ids de `BudgetRubrica` (#452): o SGD alerta quando a solicitação usa outra. */
  rubricas_previstas: number[];
};

const EMPTY_FORM: FormState = {
  numero: "",
  descricao: "",
  submeta: "",
  indicador: "",
  quantidade_planejada: "",
  valor_unitario: "",
  data_inicio: "",
  data_fim: "",
  rubricas_previstas: [],
};

function acaoToForm(a: Acao): FormState {
  return {
    numero: a.numero ?? "",
    descricao: a.descricao ?? "",
    submeta: String(a.submeta ?? ""),
    indicador: String(a.indicador ?? ""),
    // O DRF devolve "12.00"; editar não deve mostrar casas decimais que o
    // usuário não digitou. formatQtd/decOrNull fazem o ida-e-volta com vírgula.
    quantidade_planejada: formatQtd(a.quantidade_planejada),
    // O valor vem como "3500.00" e precisa voltar à máscara de digitação.
    valor_unitario: formatMoneyInput(
      String(a.valor_unitario ?? "").replace(/\D/g, ""),
    ),
    data_inicio: a.data_inicio ?? "",
    data_fim: a.data_fim ?? "",
    rubricas_previstas: a.rubricas_previstas ?? [],
  };
}

function formToPayload(f: FormState): AcaoWritePayload {
  return {
    submeta: Number(f.submeta),
    indicador: Number(f.indicador),
    numero: f.numero.trim(),
    descricao: f.descricao.trim(),
    quantidade_planejada: decOrNull(f.quantidade_planejada) ?? "0",
    valor_unitario: moneyOrNull(f.valor_unitario) ?? "0",
    data_inicio: f.data_inicio,
    data_fim: f.data_fim,
    rubricas_previstas: f.rubricas_previstas,
  };
}

/**
 * Valor total calculado no cliente, só para feedback ao digitar.
 *
 * Nunca vai no payload: `valor_total` é read_only no serializer e quem calcula
 * de verdade é o backend, com Decimal. Depois de salvar, a listagem recarrega e
 * passa a exibir o número que veio de lá.
 */
export function calcularValorTotal(f: {
  quantidade_planejada: string;
  valor_unitario: string;
}): number {
  const qtd = Number(decOrNull(f.quantidade_planejada) ?? 0);
  const unit = Number(moneyOrNull(f.valor_unitario) ?? 0);
  if (!Number.isFinite(qtd) || !Number.isFinite(unit)) return 0;
  return qtd * unit;
}

/**
 * Validação de cliente — só o que dá para checar sem ida ao servidor. A
 * unicidade do número dentro da Submeta fica no backend e volta como
 * field_error. Quantidade, valor unitário e datas são obrigatórios pela DRS
 * §5.5 (#452); a quantidade segue o `MinValueValidator(0.01)` do model.
 */
function validate(f: FormState, submetaNumero?: string): Record<string, string> {
  const errs: Record<string, string> = {};
  const numero = f.numero.trim();

  if (!numero) {
    errs.numero = "Informe o número da Ação.";
  } else if (!NUMERO_ACAO_RE.test(numero)) {
    errs.numero = "Formato inválido. Use X.Y.Z (ex: 1.1.1, 2.3.4).";
  } else if (submetaNumero && !numero.startsWith(`${submetaNumero}.`)) {
    // A mesma regra de `_erros_no_pai` no backend.
    errs.numero = `O número da Ação deve começar com ${submetaNumero}. (número da Submeta).`;
  }

  if (!f.descricao.trim()) errs.descricao = "Informe a descrição da Ação.";
  if (!f.submeta) errs.submeta = "Selecione a Submeta.";
  if (!f.indicador) errs.indicador = "Selecione o Indicador.";

  const quantidade = decOrNull(f.quantidade_planejada);
  if (!f.quantidade_planejada.trim()) {
    errs.quantidade_planejada = "Informe a quantidade planejada.";
  } else if (quantidade === null || !(Number(quantidade) > 0)) {
    errs.quantidade_planejada = "A quantidade planejada precisa ser maior que zero.";
  }
  if (moneyOrNull(f.valor_unitario) === null) {
    errs.valor_unitario = "Informe o valor unitário.";
  }

  if (!f.data_inicio) errs.data_inicio = "Informe a data de início.";
  if (!f.data_fim) errs.data_fim = "Informe a data de término.";

  // Comparação lexicográfica é segura para "YYYY-MM-DD".
  if (f.data_inicio && f.data_fim && f.data_fim < f.data_inicio) {
    errs.data_fim = "A data de término não pode ser anterior à de início.";
  }

  return errs;
}

// ─── Componente principal ────────────────────────────────────────────────────

export function AcaoSlideOver({
  open,
  onClose,
  mode,
  metaId,
  acao,
  existentes,
  rubricas,
  rubricasFalhou = false,
  onSaved,
  onPedirSubmeta,
}: Props) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [submetaOpts, setSubmetaOpts] = useState<SubmetaOption[]>([]);
  const [indicadorOpts, setIndicadorOpts] = useState<IndicadorOption[]>([]);
  const [opcoesCarregadas, setOpcoesCarregadas] = useState(false);
  /**
   * O último número que o formulário sugeriu. Enquanto o campo tiver ele (ou
   * estiver vazio), trocar a Submeta troca a sugestão; o que o usuário digitou
   * à mão nunca é sobrescrito.
   */
  const [ultimaSugestao, setUltimaSugestao] = useState<string | null>(null);

  const acaoId = acao?.id;

  // A listagem da Meta já traz a Ação completa, então "edit" não precisa
  // buscar detalhe: basta preencher o form com o que veio.
  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFieldErrors({});
    setGlobalError(null);
    setUltimaSugestao(null);
    setForm(mode === "edit" && acao ? acaoToForm(acao) : EMPTY_FORM);
  }, [open, mode, acao]);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOpcoesCarregadas(false);
    Promise.all([
      listSubmetasDaMeta(metaId, controller.signal),
      listIndicadores(controller.signal),
    ])
      .then(([submetas, indicadores]) => {
        if (controller.signal.aborted) return;
        setSubmetaOpts(submetas);
        setIndicadorOpts(indicadores);
        setOpcoesCarregadas(true);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setGlobalError("Não foi possível carregar as submetas e indicadores.");
      });
    return () => controller.abort();
  }, [open, metaId]);

  function update<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setFieldErrors((prev) => {
      if (!(field in prev)) return prev;
      const next = { ...prev };
      delete next[field as string];
      return next;
    });
  }

  function limparErros(...campos: string[]) {
    setFieldErrors((prev) => {
      if (!campos.some((c) => c in prev)) return prev;
      const next = { ...prev };
      for (const c of campos) delete next[c];
      return next;
    });
  }

  /**
   * Escolher a Submeta sugere o próximo número livre nela (#452). Na edição,
   * voltar à Submeta original devolve o número que a Ação já tem, em vez de
   * pular para o próximo.
   */
  function escolherSubmeta(valor: string) {
    const submeta = submetaOpts.find((s) => String(s.id) === valor);
    const atual = form.numero.trim();
    const automatico =
      atual === "" ||
      atual === ultimaSugestao ||
      (mode === "edit" && atual === acao?.numero);
    let numero = form.numero;
    if (submeta && automatico) {
      numero =
        mode === "edit" && acao && valor === String(acao.submeta)
          ? acao.numero
          : proximoNumeroDeAcao(
              submeta.numero,
              existentes.filter((a) => a.id !== acao?.id),
            );
      setUltimaSugestao(numero);
    }
    setForm((prev) => ({ ...prev, submeta: valor, numero }));
    limparErros("submeta", ...(numero !== form.numero ? ["numero"] : []));
  }

  function alternarRubrica(id: number) {
    update(
      "rubricas_previstas",
      form.rubricas_previstas.includes(id)
        ? form.rubricas_previstas.filter((r) => r !== id)
        : [...form.rubricas_previstas, id],
    );
  }

  const submetaEscolhida = submetaOpts.find((s) => String(s.id) === form.submeta);

  // Ativas, mais as inativas que a Ação já tem: desmarcar uma delas é possível,
  // marcar uma inativa de novo não.
  const opcoesRubrica = (rubricas ?? []).filter(
    (r) => r.ativo || form.rubricas_previstas.includes(r.id),
  );

  async function handleSave() {
    if (saving) return;

    const errs = validate(form, submetaEscolhida?.numero);
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
        mode === "edit" && acaoId
          ? await updateAcao(acaoId, payload)
          : await createAcao(payload);
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
          : "Não foi possível salvar a Ação. Tente novamente.",
      );
    } finally {
      setSaving(false);
    }
  }

  const title =
    mode === "edit" ? `Editar Ação ${acao?.numero ?? ""}`.trim() : "Nova Ação";

  const footer = (
    <div className="flex items-center justify-end gap-2">
      <Button variant="ghost" onClick={onClose} disabled={saving}>
        Cancelar
      </Button>
      <Button
        onClick={handleSave}
        loading={saving}
        data-testid="acao-form-submit"
      >
        Salvar
      </Button>
    </div>
  );

  const valorTotal = calcularValorTotal(form);

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={title}
      footer={footer}
      width="wide"
    >
      <div className="flex flex-col gap-4 px-4 py-4" data-testid="acao-form">
        {globalError && (
          <div
            role="alert"
            className="rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text"
          >
            {globalError}
          </div>
        )}

        <div data-testid="acao-form-submeta">
          {opcoesCarregadas && submetaOpts.length === 0 && (
            // Sem Submeta não há Ação: explica e leva ao cadastro (#431).
            <div
              role="status"
              className="mb-2 flex flex-col items-start gap-2 rounded-md border border-warning-text bg-warning-bg px-3 py-2.5 text-sm text-warning-text"
              data-testid="acao-form-sem-submeta"
            >
              Esta Meta ainda não tem Submetas, e toda Ação fica dentro de uma. Cadastre a Submeta primeiro.
              {onPedirSubmeta && (
                <Button size="sm" variant="secondary" onClick={onPedirSubmeta} data-testid="acao-form-nova-submeta">
                  Cadastrar submeta
                </Button>
              )}
            </div>
          )}
          <Select
            label="Submeta"
            required
            options={submetaOpts.map((s) => ({
              value: String(s.id),
              label: `${s.numero} — ${s.titulo}`,
            }))}
            value={form.submeta}
            onChange={escolherSubmeta}
            placeholder="Selecione..."
            error={fieldErrors.submeta}
            disabled={saving}
          />
        </div>

        <Input
          label="Número"
          required
          value={form.numero}
          onChange={(e) => update("numero", e.target.value)}
          error={fieldErrors.numero}
          disabled={saving}
          autoComplete="off"
          placeholder="X.Y.Z"
          helperText="Sugerido pelo próximo número livre da Submeta. Formato X.Y.Z, com X.Y igual ao número da Submeta."
          data-testid="acao-form-numero"
        />

        <Textarea
          label="Descrição"
          required
          rows={3}
          maxLength={500}
          value={form.descricao}
          onChange={(e) => update("descricao", e.target.value)}
          error={fieldErrors.descricao}
          disabled={saving}
          data-testid="acao-form-descricao"
        />

        <div data-testid="acao-form-indicador">
          <Select
            label="Indicador"
            required
            options={indicadorOpts.map((i) => ({
              value: String(i.id),
              label: `${i.codigo} — ${i.nome}`,
            }))}
            value={form.indicador}
            onChange={(v) => update("indicador", v)}
            placeholder="Selecione..."
            error={fieldErrors.indicador}
            disabled={saving}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="Quantidade planejada"
            required
            value={form.quantidade_planejada}
            onChange={(e) =>
              update("quantidade_planejada", e.target.value)
            }
            error={fieldErrors.quantidade_planejada}
            disabled={saving}
            inputMode="decimal"
            placeholder="0"
            data-testid="acao-form-quantidade"
          />
          <Input
            label="Valor unitário (R$)"
            required
            value={form.valor_unitario}
            onChange={(e) =>
              update("valor_unitario", formatMoneyInput(e.target.value))
            }
            error={fieldErrors.valor_unitario}
            disabled={saving}
            inputMode="numeric"
            placeholder="R$ 0,00"
            data-testid="acao-form-valor-unitario"
          />
        </div>

        {/* Cálculo em tempo real: some do payload, serve só de conferência
            enquanto se digita. */}
        <div
          className="flex items-baseline justify-between gap-3 rounded-md border border-border bg-surface-muted px-3 py-2.5"
          data-testid="acao-form-valor-total"
        >
          <span className="text-sm text-text-muted">Valor total</span>
          <span className="text-base font-semibold tabular-nums text-text">
            {formatCurrencyBRL(valorTotal)}
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="Data de início"
            required
            type="date"
            value={form.data_inicio}
            onChange={(e) => update("data_inicio", e.target.value)}
            error={fieldErrors.data_inicio}
            disabled={saving}
            data-testid="acao-form-data-inicio"
          />
          <Input
            label="Data de término"
            required
            type="date"
            value={form.data_fim}
            onChange={(e) => update("data_fim", e.target.value)}
            error={fieldErrors.data_fim}
            disabled={saving}
            data-testid="acao-form-data-fim"
          />
        </div>

        <fieldset className="flex flex-col gap-1" data-testid="acao-form-rubricas">
          <legend className="text-label font-medium leading-[1.2] text-text">Rubricas previstas</legend>
          <p className="text-2xs text-text-muted">
            O SGD avisa quando uma solicitação desta Ação usar outra rubrica. Sem nenhuma marcada, não há aviso.
          </p>
          {rubricasFalhou ? (
            <span role="alert" className="mt-1 text-2xs text-error-text">
              Não foi possível carregar as rubricas do orçamento.
            </span>
          ) : rubricas === undefined ? (
            <span className="mt-1 text-sm text-text-muted">Carregando rubricas…</span>
          ) : (
            <div className="mt-1 grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
              {opcoesRubrica.map((r) => (
                <label key={r.id} className="flex items-center gap-2 text-sm text-text">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-[var(--color-primary)]"
                    checked={form.rubricas_previstas.includes(r.id)}
                    onChange={() => alternarRubrica(r.id)}
                    disabled={saving}
                    data-testid={`acao-form-rubrica-${r.id}`}
                  />
                  {r.ativo ? r.nome : `${r.nome} (inativa)`}
                </label>
              ))}
            </div>
          )}
          {fieldErrors.rubricas_previstas && (
            <span role="alert" className="text-2xs text-error-text">
              {fieldErrors.rubricas_previstas}
            </span>
          )}
        </fieldset>
      </div>
    </SlideOver>
  );
}
