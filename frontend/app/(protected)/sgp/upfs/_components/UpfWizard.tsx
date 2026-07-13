"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircleIcon } from "@/app/components/icons";
import { Button } from "@/app/components/ui/Button/Button";
import type { SelectOption } from "@/app/components/ui/Select/Select";
import { ApiError } from "@/app/lib/api";
import {
  createUpf,
  fetchComunidadeOptions,
  fetchMunicipalitiesByState,
  fetchMunicipality,
  fetchProjetoOptions,
  fetchStateOptions,
  fetchTerritoryMap,
  updateUpf,
  type MunicipalityOpt,
  type UpfDetail,
} from "@/app/lib/upfs";
import { isValidCpf, isValidPhone } from "@/app/lib/format";
import { absoluteDateTime } from "@/app/lib/datetime";
import {
  detailToForm,
  EMPTY_FORM,
  FIELD_STEP,
  formToPayload,
  STEP_LABELS,
  type UpfFormData,
} from "./upfForm";
import { Stepper } from "./Stepper";
import { ComunidadeModal } from "./ComunidadeModal";
import { useUpfDraft } from "./useUpfDraft";
import {
  CREATE_COMUNIDADE_VALUE,
  LocalizacaoStep,
} from "./steps/LocalizacaoStep";
import { DadosBasicosStep } from "./steps/DadosBasicosStep";
import { ComunicacaoStep } from "./steps/ComunicacaoStep";
import { MoradiaStep } from "./steps/MoradiaStep";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const FOCUS_SELECTOR =
  'input:not([type="hidden"]):not([disabled]), textarea:not([disabled]), [role="combobox"]:not([disabled])';

type UpfWizardProps = {
  mode: "create" | "edit";
  upfId?: string;
  initialData?: UpfDetail;
};

function unionOption(
  options: SelectOption[],
  current: SelectOption,
): SelectOption[] {
  return options.some((o) => o.value === current.value)
    ? options
    : [current, ...options];
}

/** Erros do passo indicado (obrigatórios + formatos). */
function validateStep(step: number, form: UpfFormData): Record<string, string> {
  const errs: Record<string, string> = {};
  if (step === 0) {
    if (!form.estado) errs.estado = "Selecione o estado.";
    if (!form.municipio) errs.municipio = "Selecione o município.";
    // Projeto é opcional por ora (não há endpoint de cadastro de projetos);
    // voltará a ser obrigatório quando o backend expuser a listagem.
  }
  if (step === 1) {
    if (!form.nome_titular.trim())
      errs.nome_titular = "Informe o nome do titular.";
    if (!form.cpf.trim()) errs.cpf = "Informe o CPF.";
    else if (!isValidCpf(form.cpf)) errs.cpf = "CPF inválido.";
  }
  if (step === 2) {
    if (form.email.trim() && !EMAIL_RE.test(form.email.trim())) {
      errs.email = "Informe um e-mail válido.";
    }
    if (form.telefone.trim() && !isValidPhone(form.telefone)) {
      errs.telefone = "Telefone incompleto. Use DDD + número.";
    }
    if (form.whatsapp.trim() && !isValidPhone(form.whatsapp)) {
      errs.whatsapp = "WhatsApp incompleto. Use DDD + número.";
    }
  }
  return errs;
}

export function UpfWizard({ mode, upfId, initialData }: UpfWizardProps) {
  const router = useRouter();
  const draftKey = mode === "edit" ? String(upfId) : "novo";
  const { existing, save, clear } = useUpfDraft(draftKey);

  const [form, setForm] = useState<UpfFormData>(() =>
    initialData ? detailToForm(initialData) : EMPTY_FORM,
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [currentStep, setCurrentStep] = useState(0);
  const [furthest, setFurthest] = useState(mode === "edit" ? 3 : 0);

  const [estadoOptions, setEstadoOptions] = useState<SelectOption[]>([]);
  const [municipioOptions, setMunicipioOptions] = useState<MunicipalityOpt[]>(
    [],
  );
  const [comunidadeOptions, setComunidadeOptions] = useState<SelectOption[]>([]);
  const [projetoOptions, setProjetoOptions] = useState<SelectOption[]>(() =>
    initialData
      ? [
          {
            value: String(initialData.projeto.id),
            label: initialData.projeto.nome,
          },
        ]
      : [],
  );
  const [territorioMap, setTerritorioMap] = useState<Map<number, string>>(
    new Map(),
  );

  const [comunidadeModalOpen, setComunidadeModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [draftDismissed, setDraftDismissed] = useState(false);

  const stepRef = useRef<HTMLDivElement | null>(null);
  const dirty = useRef(false);

  // Carrega opções que não dependem de cascata (estados, projetos, territórios).
  useEffect(() => {
    const controller = new AbortController();
    fetchStateOptions(controller.signal)
      .then(setEstadoOptions)
      .catch(() => {});
    fetchTerritoryMap(controller.signal)
      .then(setTerritorioMap)
      .catch(() => {});
    fetchProjetoOptions(controller.signal)
      .then((fetched) => {
        setProjetoOptions((prev) => {
          const base = fetched.length > 0 ? fetched : prev;
          return initialData
            ? unionOption(base, {
                value: String(initialData.projeto.id),
                label: initialData.projeto.nome,
              })
            : base;
        });
      })
      .catch(() => {});
    return () => controller.abort();
  }, [initialData]);

  // Carrega as opções de cascata para um formulário já preenchido (edição/rascunho).
  const hydrateCascade = useCallback(async (data: UpfFormData) => {
    if (data.estado) {
      const munis = await fetchMunicipalitiesByState(data.estado).catch(
        () => [] as MunicipalityOpt[],
      );
      setMunicipioOptions(munis);
    }
    if (data.municipio) {
      const comus = await fetchComunidadeOptions(data.municipio).catch(
        () => [] as SelectOption[],
      );
      setComunidadeOptions(comus);
    }
  }, []);

  // Prefill de edição: descobre o estado a partir do município e hidrata a cascata.
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

  // Salva rascunho a cada mudança (após a primeira interação do usuário).
  useEffect(() => {
    if (dirty.current) save(form);
  }, [form, save]);

  const focusFirstField = useCallback(() => {
    requestAnimationFrame(() => {
      const el = stepRef.current?.querySelector<HTMLElement>(FOCUS_SELECTOR);
      el?.focus();
    });
  }, []);

  const patchForm = useCallback((patch: Partial<UpfFormData>) => {
    dirty.current = true;
    setForm((prev) => ({ ...prev, ...patch }));
    setErrors((prev) => {
      if (Object.keys(patch).every((k) => !(k in prev))) return prev;
      const next = { ...prev };
      for (const k of Object.keys(patch)) delete next[k];
      return next;
    });
  }, []);

  function handleEstadoChange(value: string) {
    dirty.current = true;
    setForm((prev) => ({ ...prev, estado: value, municipio: "", comunidade: "" }));
    setErrors((prev) => ({ ...prev, estado: "", municipio: "" }));
    setMunicipioOptions([]);
    setComunidadeOptions([]);
    if (value) {
      fetchMunicipalitiesByState(value)
        .then(setMunicipioOptions)
        .catch(() => setMunicipioOptions([]));
    }
  }

  function handleMunicipioChange(value: string) {
    dirty.current = true;
    setForm((prev) => ({ ...prev, municipio: value, comunidade: "" }));
    setErrors((prev) => ({ ...prev, municipio: "" }));
    setComunidadeOptions([]);
    if (value) {
      fetchComunidadeOptions(value)
        .then(setComunidadeOptions)
        .catch(() => setComunidadeOptions([]));
    }
  }

  function handleComunidadeChange(value: string) {
    if (value === CREATE_COMUNIDADE_VALUE) {
      setComunidadeModalOpen(true);
      return;
    }
    patchForm({ comunidade: value });
  }

  function handleComunidadeCreated(option: SelectOption) {
    setComunidadeOptions((prev) => [...prev, option]);
    patchForm({ comunidade: option.value });
    setComunidadeModalOpen(false);
  }

  // Território derivado do município selecionado.
  const selectedMuni = municipioOptions.find((o) => o.value === form.municipio);
  let territorioNome = "";
  let territorioWarning = false;
  if (selectedMuni) {
    territorioNome =
      selectedMuni.territoryId != null
        ? (territorioMap.get(selectedMuni.territoryId) ?? "")
        : "";
    territorioWarning = selectedMuni.territoryId == null;
  } else if (
    initialData &&
    String(initialData.municipio.id) === form.municipio
  ) {
    territorioNome = initialData.territorio?.nome ?? "";
  }

  function goToStep(index: number) {
    setCurrentStep(index);
    focusFirstField();
  }

  function handleNext() {
    const errs = validateStep(currentStep, form);
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      focusFirstField();
      return;
    }
    setErrors({});
    const next = Math.min(currentStep + 1, STEP_LABELS.length - 1);
    setFurthest((f) => Math.max(f, next));
    goToStep(next);
  }

  function handleBack() {
    goToStep(Math.max(currentStep - 1, 0));
  }

  async function handleSubmit() {
    // Valida todos os passos; salta para o primeiro com erro.
    const allErrors: Record<string, string> = {};
    for (let s = 0; s < STEP_LABELS.length; s++) {
      Object.assign(allErrors, validateStep(s, form));
    }
    if (Object.keys(allErrors).length > 0) {
      setErrors(allErrors);
      const firstStep = Math.min(
        ...Object.keys(allErrors).map((f) => FIELD_STEP[f] ?? 3),
      );
      goToStep(firstStep);
      return;
    }

    setSubmitting(true);
    setGlobalError(null);
    try {
      const payload = formToPayload(form);
      const result =
        mode === "edit" && upfId
          ? await updateUpf(upfId, payload)
          : await createUpf(payload);
      clear();
      router.push(`/sgp/upfs/${result.id}/`);
    } catch (e) {
      if (e instanceof ApiError && e.fieldErrors?.length) {
        const mapped: Record<string, string> = {};
        for (const fe of e.fieldErrors) mapped[fe.field] = fe.message;
        setErrors(mapped);
        const firstStep = Math.min(
          ...Object.keys(mapped).map((f) => FIELD_STEP[f] ?? 3),
        );
        setCurrentStep(firstStep);
        if (mapped.cpf) {
          requestAnimationFrame(() =>
            document.getElementById("upf-cpf")?.focus(),
          );
        } else {
          focusFirstField();
        }
        setGlobalError("Corrija os campos destacados e tente novamente.");
      } else {
        setGlobalError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível salvar a UPF. Tente novamente.",
        );
      }
      setSubmitting(false);
    }
  }

  function continueDraft() {
    if (!existing) return;
    dirty.current = true;
    setForm(existing.data);
    setDraftDismissed(true);
    hydrateCascade(existing.data);
  }

  function discardDraft() {
    clear();
    setDraftDismissed(true);
  }

  const showDraftPrompt = existing && !draftDismissed;

  return (
    <div className="space-y-6">
      {showDraftPrompt && (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-info-text/30 bg-info-bg px-4 py-3"
        >
          <p className="text-sm text-info-text">
            Há um rascunho salvo em {absoluteDateTime(existing.at)}. Deseja
            continuar de onde parou?
          </p>
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={continueDraft}>
              Continuar rascunho
            </Button>
            <Button size="sm" variant="ghost" onClick={discardDraft}>
              Descartar
            </Button>
          </div>
        </div>
      )}

      <Stepper
        steps={STEP_LABELS}
        current={currentStep}
        furthest={furthest}
        onStepClick={goToStep}
      />

      {globalError && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg bg-error-bg px-4 py-3"
        >
          <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-error-text" />
          <p className="text-sm text-error-text">{globalError}</p>
        </div>
      )}

      <div ref={stepRef} className="rounded-lg border border-border bg-surface p-6">
        {currentStep === 0 && (
          <LocalizacaoStep
            form={form}
            errors={errors}
            onChange={patchForm}
            estadoOptions={estadoOptions}
            municipioOptions={municipioOptions}
            comunidadeOptions={comunidadeOptions}
            projetoOptions={projetoOptions}
            territorioNome={territorioNome}
            territorioWarning={territorioWarning}
            onEstadoChange={handleEstadoChange}
            onMunicipioChange={handleMunicipioChange}
            onComunidadeChange={handleComunidadeChange}
            onGps={(lat, lng) => patchForm({ latitude: lat, longitude: lng })}
          />
        )}
        {currentStep === 1 && (
          <DadosBasicosStep form={form} errors={errors} onChange={patchForm} />
        )}
        {currentStep === 2 && (
          <ComunicacaoStep form={form} errors={errors} onChange={patchForm} />
        )}
        {currentStep === 3 && (
          <MoradiaStep form={form} errors={errors} onChange={patchForm} />
        )}
      </div>

      <div className="flex items-center justify-between gap-3">
        <div>
          {currentStep > 0 && (
            <Button variant="secondary" onClick={handleBack} disabled={submitting}>
              Voltar
            </Button>
          )}
        </div>
        <div className="flex items-center gap-2">
          {currentStep < STEP_LABELS.length - 1 ? (
            <Button onClick={handleNext}>Avançar</Button>
          ) : (
            <Button onClick={handleSubmit} loading={submitting}>
              Salvar
            </Button>
          )}
        </div>
      </div>

      {form.municipio && (
        <ComunidadeModal
          open={comunidadeModalOpen}
          onClose={() => setComunidadeModalOpen(false)}
          municipioId={form.municipio}
          onCreated={handleComunidadeCreated}
        />
      )}
    </div>
  );
}
