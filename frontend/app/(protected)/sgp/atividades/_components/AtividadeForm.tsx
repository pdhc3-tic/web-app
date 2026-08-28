"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { AlertCircleIcon } from "@/app/components/icons";
import Spinner from "@/app/components/icons/Spinner";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select, type SelectOption } from "@/app/components/ui/Select/Select";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import {
  STATUS_INICIAIS,
  createAtividade,
  getAtividade,
  listAcoes,
  listTecnicos,
  statusLabel,
  updateAtividade,
  type AcaoPT,
  type AtividadeDetail,
  type TecnicoOption,
} from "@/app/lib/atividades";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";
import {
  fetchComunidadeOptions,
  fetchMunicipalitiesByState,
  fetchMunicipality,
  fetchStateOptions,
  getUpfDetail,
  type MunicipalityOpt,
} from "@/app/lib/upfs";
// Reaproveitado do wizard de UPF — mesmo comportamento de captura de GPS.
import { GpsCapture } from "../../upfs/_components/GpsCapture";
import { EvidenceGallery } from "@/app/components/sgp/EvidenceGallery/EvidenceGallery";
import { AcaoCombobox } from "./AcaoCombobox";
import { EquipeAdicionalPicker } from "./EquipeAdicionalPicker";
import { ParticipantesSection } from "./ParticipantesSection";
import {
  EMPTY_FORM,
  detailToForm,
  exigeJustificativa,
  fieldId,
  firstErrorField,
  formToPayload,
  validate,
  type AtividadeFormData,
} from "./formModel";

type Props = {
  mode: "create" | "edit";
  atividadeId?: string;
  initialData?: AtividadeDetail;
  /**
   * Pré-preenchimento parcial para o modo "create" (ex.: data vinda do
   * calendário). Ignorado em "edit" — o detalhe já traz tudo.
   */
  initialFormPatch?: Partial<AtividadeFormData>;
};

const LOADING_LABEL = "Carregando atividades…";

export function AtividadeForm({
  mode,
  atividadeId,
  initialData,
  initialFormPatch,
}: Props) {
  const router = useRouter();
  const { showToast } = useToast();
  const { data: session } = useSession();
  const choices = useSgpChoices();

  const [form, setForm] = useState<AtividadeFormData>(() => {
    if (initialData) return detailToForm(initialData);
    if (initialFormPatch) return { ...EMPTY_FORM, ...initialFormPatch };
    return EMPTY_FORM;
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [cancelConfirmOpen, setCancelConfirmOpen] = useState(false);
  const [dirty, setDirty] = useState(false);

  // Dados relacionados
  const [acoes, setAcoes] = useState<AcaoPT[]>([]);
  const [tecnicos, setTecnicos] = useState<TecnicoOption[]>([]);
  const [estadoOptions, setEstadoOptions] = useState<SelectOption[]>([]);
  const [municipioOptions, setMunicipioOptions] = useState<MunicipalityOpt[]>([]);
  const [comunidadeOptions, setComunidadeOptions] = useState<SelectOption[]>([]);
  const [relacionadosLoading, setRelacionadosLoading] = useState(true);

  // ── Carga dos dados relacionados (ações, técnicos, estados) ───────────────
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      listAcoes(controller.signal).catch(() => [] as AcaoPT[]),
      listTecnicos(controller.signal),
      fetchStateOptions(controller.signal).catch(() => [] as SelectOption[]),
    ])
      .then(([acoesData, tecnicosData, estadosData]) => {
        if (controller.signal.aborted) return;
        setAcoes(acoesData);
        setTecnicos(tecnicosData);
        setEstadoOptions(estadosData);
      })
      .finally(() => {
        if (!controller.signal.aborted) setRelacionadosLoading(false);
      });
    return () => controller.abort();
  }, []);

  // ── Prefill de edição: estado a partir do município + cascata ─────────────
  useEffect(() => {
    if (mode !== "edit" || !initialData) return;
    let active = true;
    (async () => {
      try {
        const muni = await fetchMunicipality(initialData.municipio.id);
        if (!active) return;
        const estado = String(muni.state);
        setForm((prev) => ({ ...prev, estado }));
        const [munis, comus] = await Promise.all([
          fetchMunicipalitiesByState(estado).catch(
            () => [] as MunicipalityOpt[],
          ),
          initialData.comunidade
            ? fetchComunidadeOptions(initialData.municipio.id).catch(
                () => [] as SelectOption[],
              )
            : Promise.resolve([] as SelectOption[]),
        ]);
        if (!active) return;
        setMunicipioOptions(munis);
        setComunidadeOptions(comus);
      } catch {
        /* mantém o que já foi preenchido */
      }
    })();
    return () => {
      active = false;
    };
  }, [mode, initialData]);

  // ── Prefill de edição: rótulos das UPFs participantes ─────────────────────
  // O detalhe devolve só os ids; buscamos cada UPF para exibir nome e CPF.
  useEffect(() => {
    if (mode !== "edit" || !initialData) return;
    const ids = initialData.upfs_participantes;
    if (ids.length === 0) return;

    let active = true;
    Promise.all(
      ids.map((id) =>
        getUpfDetail(id)
          .then((upf) => ({
            id: upf.id,
            nome: upf.titular.nome_completo,
            cpf: upf.titular.cpf,
          }))
          .catch(() => ({ id, nome: `UPF #${id}`, cpf: "" })),
      ),
    ).then((refs) => {
      if (!active) return;
      setForm((prev) => ({ ...prev, upfs_participantes: refs }));
    });
    return () => {
      active = false;
    };
  }, [mode, initialData]);

  const patchForm = useCallback((patch: Partial<AtividadeFormData>) => {
    setDirty(true);
    setForm((prev) => ({ ...prev, ...patch }));
    setErrors((prev) => {
      if (Object.keys(patch).every((k) => !(k in prev))) return prev;
      const next = { ...prev };
      for (const k of Object.keys(patch)) delete next[k];
      return next;
    });
  }, []);

  function handleEstadoChange(value: string) {
    setDirty(true);
    setForm((prev) => ({
      ...prev,
      estado: value,
      municipio: "",
      comunidade: "",
    }));
    setErrors((prev) => ({ ...prev, municipio: "" }));
    setMunicipioOptions([]);
    setComunidadeOptions([]);
    if (value) {
      fetchMunicipalitiesByState(value)
        .then(setMunicipioOptions)
        .catch(() => setMunicipioOptions([]));
    }
  }

  function handleMunicipioChange(value: string) {
    setDirty(true);
    setForm((prev) => ({ ...prev, municipio: value, comunidade: "" }));
    setErrors((prev) => ({ ...prev, municipio: "" }));
    setComunidadeOptions([]);
    if (value) {
      fetchComunidadeOptions(value)
        .then(setComunidadeOptions)
        .catch(() => setComunidadeOptions([]));
    }
  }

  const sessionUser = session?.user;

  // Na criação o responsável começa no usuário logado. É derivado, e não
  // gravado no estado, porque a sessão só chega depois do primeiro render —
  // gravá-la exigiria um setState dentro de efeito.
  const tecnicoResponsavel =
    form.tecnico_responsavel || (mode === "create" ? (sessionUser?.id ?? "") : "");

  /** Formulário com os defaults derivados aplicados — base para validar e salvar. */
  const effectiveForm = useMemo<AtividadeFormData>(
    () => ({ ...form, tecnico_responsavel: tecnicoResponsavel }),
    [form, tecnicoResponsavel],
  );

  // ── Status permitidos ─────────────────────────────────────────────────────
  // Criação: só 'planejado' e 'agendado' (regra do serializer).
  // Edição: o status atual + as transições que o backend declara permitidas.
  const statusOptions = useMemo<SelectOption[]>(() => {
    if (mode === "create") {
      return choices.status.filter((s) => STATUS_INICIAIS.includes(s.value));
    }
    const permitidos = new Set([
      form.status,
      ...(initialData?.transicoes_permitidas ?? []),
    ]);
    return choices.status.filter((s) => permitidos.has(s.value));
  }, [mode, choices.status, form.status, initialData?.transicoes_permitidas]);

  const tecnicoOptions = useMemo<SelectOption[]>(() => {
    const base = tecnicos.map((t) => ({
      value: String(t.id),
      label: t.nome,
    }));
    if (base.length > 0) return base;
    // Modo degradado: o endpoint de usuários é restrito a Super Admin, então
    // resta oferecer o próprio usuário logado (ou o responsável já gravado).
    const fallback: SelectOption[] = [];
    if (sessionUser?.id) {
      fallback.push({
        value: sessionUser.id,
        label: sessionUser.nome_completo ?? "Você",
      });
    }
    if (
      initialData &&
      !fallback.some((o) => o.value === String(initialData.tecnico_responsavel.id))
    ) {
      fallback.push({
        value: String(initialData.tecnico_responsavel.id),
        label: initialData.tecnico_responsavel.nome,
      });
    }
    return fallback;
  }, [tecnicos, sessionUser, initialData]);

  const mostrarJustificativa = exigeJustificativa(form.status);

  // ── Submit ────────────────────────────────────────────────────────────────
  function focusField(field: string) {
    requestAnimationFrame(() => {
      const el = document.getElementById(fieldId(field));
      el?.focus();
      el?.scrollIntoView({ block: "center", behavior: "smooth" });
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;

    const errs = validate(effectiveForm);
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      setGlobalError("Corrija os campos destacados e tente novamente.");
      const primeiro = firstErrorField(errs);
      if (primeiro) focusField(primeiro);
      return;
    }

    setErrors({});
    setGlobalError(null);
    setSubmitting(true);

    try {
      const payload = formToPayload(effectiveForm);
      const salva =
        mode === "edit" && atividadeId
          ? await updateAtividade(atividadeId, payload)
          : await createAtividade(payload);

      showToast("Atividade salva.", "success");
      setDirty(false);

      if (mode === "edit") {
        // Em edição já estamos na URL de destino: o push seria no-op, e como o
        // reset de `submitting` dependia da navegação o botão ficava preso em
        // "Salvando". Libera o botão e só reidrata os dados desta página.
        setSubmitting(false);
        router.refresh();
        return;
      }

      // Criação: segue para a tela de edição da atividade recém-criada. O
      // `submitting` continua true de propósito até a navegação desmontar o form.
      router.push(`/sgp/atividades/${salva.id}/editar/`);
      router.refresh();
    } catch (err) {
      setSubmitting(false);

      if (err instanceof ApiError && err.fieldErrors?.length) {
        const mapped: Record<string, string> = {};
        for (const fe of err.fieldErrors) mapped[fe.field] = fe.message;
        setErrors(mapped);
        setGlobalError(err.message);
        showToast(err.message, "error");
        const primeiro = firstErrorField(mapped);
        if (primeiro) focusField(primeiro);
        return;
      }

      const message =
        err instanceof ApiError
          ? err.message
          : "Não foi possível salvar a atividade. Tente novamente.";
      setGlobalError(message);
      showToast(message, "error");
    }
  }

  function handleCancel() {
    if (submitting) return;
    if (dirty) setCancelConfirmOpen(true);
    else router.push("/sgp/");
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">
      {relacionadosLoading && (
        <p
          role="status"
          className="flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-3 text-sm text-text-muted"
        >
          <Spinner className="h-4 w-4 animate-spin" />
          {LOADING_LABEL}
        </p>
      )}

      {globalError && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg bg-error-bg px-4 py-3"
        >
          <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-error-text" />
          <p className="text-sm text-error-text">{globalError}</p>
        </div>
      )}

      {/* ── Identificação ────────────────────────────────────────────────── */}
      <Section title="Identificação">
        <Input
          id={fieldId("titulo")}
          label="Título"
          required
          maxLength={255}
          value={form.titulo}
          onChange={(e) => patchForm({ titulo: e.target.value })}
          error={errors.titulo}
          className="sm:col-span-2"
        />
        <Select
          id={fieldId("tipo_atividade")}
          label="Tipo de atividade"
          required
          options={choices.tipo_atividade}
          value={form.tipo_atividade}
          onChange={(v) => patchForm({ tipo_atividade: v })}
          error={errors.tipo_atividade}
        />
        <Select
          id={fieldId("forma_atuacao")}
          label="Forma de atuação"
          required
          options={choices.forma_atuacao}
          value={form.forma_atuacao}
          onChange={(v) => patchForm({ forma_atuacao: v })}
          error={errors.forma_atuacao}
        />
        <div className="sm:col-span-2">
          <AcaoCombobox
            id={fieldId("acao")}
            required
            acoes={acoes}
            value={form.acao}
            onChange={(acao) => patchForm({ acao })}
            loading={relacionadosLoading}
            error={errors.acao}
          />
        </div>
      </Section>

      {/* ── Equipe ───────────────────────────────────────────────────────── */}
      <Section title="Equipe">
        <Select
          id={fieldId("tecnico_responsavel")}
          label="Técnico responsável"
          required
          options={tecnicoOptions}
          value={tecnicoResponsavel}
          onChange={(v) => patchForm({ tecnico_responsavel: v })}
          error={errors.tecnico_responsavel}
          disabled={relacionadosLoading}
        />
        <EquipeAdicionalPicker
          id={fieldId("equipe_adicional")}
          opcoes={tecnicos}
          value={form.equipe_adicional}
          onChange={(ids) => patchForm({ equipe_adicional: ids })}
          loading={relacionadosLoading}
          excluirId={tecnicoResponsavel ? Number(tecnicoResponsavel) : undefined}
        />
      </Section>

      {/* ── Localização ──────────────────────────────────────────────────── */}
      <Section title="Localização">
        <Select
          id={fieldId("estado")}
          label="Estado"
          options={estadoOptions}
          value={form.estado}
          onChange={handleEstadoChange}
          error={errors.estado}
          disabled={relacionadosLoading}
          helperText="Define quais municípios ficam disponíveis."
        />
        <Select
          id={fieldId("municipio")}
          label="Município"
          required
          options={municipioOptions}
          value={form.municipio}
          onChange={handleMunicipioChange}
          error={errors.municipio}
          disabled={!form.estado}
        />
        <Select
          id={fieldId("comunidade")}
          label="Comunidade"
          options={comunidadeOptions}
          value={form.comunidade}
          onChange={(v) => patchForm({ comunidade: v })}
          error={errors.comunidade}
          disabled={!form.municipio}
        />
        <Select
          id={fieldId("ambito")}
          label="Âmbito"
          required
          options={choices.ambito}
          value={form.ambito}
          onChange={(v) => patchForm({ ambito: v })}
          error={errors.ambito}
        />
        <div className="sm:col-span-2">
          <GpsCapture
            latitude={form.latitude}
            longitude={form.longitude}
            onCapture={(lat, lng) => patchForm({ latitude: lat, longitude: lng })}
          />
        </div>
        <Input
          id={fieldId("latitude")}
          label="Latitude"
          inputMode="decimal"
          placeholder="-8.0476"
          value={form.latitude}
          onChange={(e) => patchForm({ latitude: e.target.value })}
          error={errors.latitude}
        />
        <Input
          id={fieldId("longitude")}
          label="Longitude"
          inputMode="decimal"
          placeholder="-34.8770"
          value={form.longitude}
          onChange={(e) => patchForm({ longitude: e.target.value })}
          error={errors.longitude}
        />
      </Section>

      {/* ── Período ──────────────────────────────────────────────────────── */}
      <Section title="Período">
        <Input
          id={fieldId("data_inicio")}
          label="Data de início"
          type="date"
          required
          value={form.data_inicio}
          onChange={(e) => patchForm({ data_inicio: e.target.value })}
          error={errors.data_inicio}
        />
        <Input
          id={fieldId("data_fim")}
          label="Data de fim"
          type="date"
          required
          value={form.data_fim}
          onChange={(e) => patchForm({ data_fim: e.target.value })}
          error={errors.data_fim}
        />
      </Section>

      {/* ── Participantes ────────────────────────────────────────────────── */}
      <Section title="Participantes" columns={1}>
        <ParticipantesSection
          upfs={form.upfs_participantes}
          membros={form.membros_participantes}
          onChange={patchForm}
          errors={errors}
        />
      </Section>

      {/* ── Parceiros e narrativa ────────────────────────────────────────── */}
      <Section title="Parceiros e narrativa" columns={1}>
        <Textarea
          id={fieldId("parceiros")}
          label="Parceiros"
          rows={2}
          value={form.parceiros}
          onChange={(e) => patchForm({ parceiros: e.target.value })}
          error={errors.parceiros}
          helperText="Um parceiro por linha ou separados por vírgula."
        />
        <Textarea
          id={fieldId("descricao_narrativa")}
          label="Descrição narrativa"
          required
          rows={5}
          value={form.descricao_narrativa}
          onChange={(e) => patchForm({ descricao_narrativa: e.target.value })}
          error={errors.descricao_narrativa}
        />
        <Textarea
          id={fieldId("resultados_alcancados")}
          label="Resultados alcançados"
          rows={4}
          value={form.resultados_alcancados}
          onChange={(e) => patchForm({ resultados_alcancados: e.target.value })}
          error={errors.resultados_alcancados}
        />
      </Section>

      {/* ── Evidências (só faz sentido após a atividade existir) ───────────── */}
      {mode === "edit" && atividadeId && (
        <Section title="Evidências" columns={1}>
          <EvidenceGallery atividadeId={atividadeId} />
        </Section>
      )}

      {/* ── Status ───────────────────────────────────────────────────────── */}
      <Section title="Status">
        <Select
          id={fieldId("status")}
          label="Status"
          required
          options={statusOptions}
          value={form.status}
          onChange={(v) => patchForm({ status: v })}
          error={errors.status}
          helperText={
            mode === "create"
              ? "Novas atividades começam como Planejado ou Agendado."
              : `Transições permitidas a partir de ${statusLabel(initialData?.status ?? form.status)}.`
          }
        />
        {mostrarJustificativa && (
          <div className="sm:col-span-2">
            <Textarea
              id={fieldId("justificativa")}
              label="Justificativa"
              required
              rows={3}
              value={form.justificativa}
              onChange={(e) => patchForm({ justificativa: e.target.value })}
              error={errors.justificativa}
              helperText="Obrigatória para os status Não realizada e Cancelada."
            />
          </div>
        )}
      </Section>

      {/* ── Ações ────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="ghost"
          onClick={handleCancel}
          disabled={submitting}
        >
          Cancelar
        </Button>
        <Button type="submit" loading={submitting}>
          Salvar
        </Button>
      </div>

      <SlideOver
        open={cancelConfirmOpen}
        onClose={() => setCancelConfirmOpen(false)}
        title={
          mode === "edit" ? "Descartar alterações?" : "Descartar atividade?"
        }
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={() => setCancelConfirmOpen(false)}>
              Continuar editando
            </Button>
            <Button variant="danger" onClick={() => router.push("/sgp/")}>
              Descartar
            </Button>
          </div>
        }
      >
        <div className="flex items-start gap-3 px-4 py-6">
          <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertCircleIcon className="h-5 w-5" />
          </span>
          <p className="text-sm leading-relaxed text-text">
            As informações não salvas serão descartadas.
          </p>
        </div>
      </SlideOver>
    </form>
  );
}

function Section({
  title,
  columns = 2,
  children,
}: {
  title: string;
  columns?: 1 | 2;
  children: React.ReactNode;
}) {
  return (
    <fieldset className="rounded-lg border border-border bg-surface p-6">
      <legend className="px-2 text-sm font-medium text-text">{title}</legend>
      <div
        className={`grid gap-4 ${columns === 2 ? "sm:grid-cols-2" : "grid-cols-1"}`}
      >
        {children}
      </div>
    </fieldset>
  );
}

/** Carrega o detalhe da atividade no client para a tela de edição. */
export function useAtividadeDetail(id: string) {
  const [data, setData] = useState<AtividadeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getAtividade(id, controller.signal)
      .then((detalhe) => {
        if (!controller.signal.aborted) setData(detalhe);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setError(
          err instanceof ApiError
            ? err.message
            : "Não foi possível carregar a atividade.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [id]);

  return { data, loading, error };
}
