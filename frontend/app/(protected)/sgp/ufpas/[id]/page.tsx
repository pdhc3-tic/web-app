"use client";

import { useEffect, useMemo, useState } from "react";
import { notFound, useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { Tabs, type TabItem } from "@/app/components/ui/Tabs/Tabs";
import { ApiError } from "@/app/lib/api";
import { getUfpaDetail, type UfpaDetail } from "@/app/lib/ufpas";
import { formatDate } from "@/app/lib/datetime";
import {
  formatArea,
  formatBool,
  formatCep,
  formatPhone,
  maskCpf,
} from "@/app/lib/format";
import { useSgpChoices } from "@/app/providers/SgpChoicesProvider";
import type { SgpChoices } from "@/app/lib/choices";
import { labelForValue } from "../_components/ufpaFormOptions";
import { UfpaHeader } from "./_components/UfpaHeader";
import { UfpaDetailSkeleton } from "./_components/UfpaDetailSkeleton";
import { DocumentosTab } from "./_components/DocumentosTab";
import { FormulariosTab } from "./_components/FormulariosTab";
import { HistoricoTab } from "./_components/HistoricoTab";
import { MembrosTab } from "./_components/MembrosTab";
import { ProducaoTab } from "./_components/ProducaoTab";

const TAB_IDS = [
  "localizacao",
  "dados-basicos",
  "comunicacao",
  "moradia",
  "membros",
  "producao",
  "documentos",
  "formularios",
  "historico",
] as const;
type TabId = (typeof TAB_IDS)[number];

type Status = "loading" | "ok" | "notfound" | "forbidden" | "error";

function joinAddress(ufpa: UfpaDetail): string {
  const line = [ufpa.logradouro, ufpa.numero].filter(Boolean).join(", ");
  return [line, ufpa.complemento, ufpa.bairro].filter(Boolean).join(" · ");
}

function gps(ufpa: UfpaDetail): string {
  return ufpa.latitude && ufpa.longitude
    ? `${ufpa.latitude}, ${ufpa.longitude}`
    : "";
}

function buildTabs(ufpa: UfpaDetail, choices: SgpChoices): TabItem[] {
  const seguridade =
    ufpa.seguridade_social.length > 0 ? (
      <div className="flex flex-wrap gap-1.5">
        {ufpa.seguridade_social.map((s) => (
          <Chip key={s}>{s}</Chip>
        ))}
      </div>
    ) : undefined;

  // Estado vem embutido em `ufpa.municipio.estado` (contrato do
  // `MunicipioNestedSerializer`). Quando o backend deixa de enviar essa chave
  // — cadastro legado, resposta parcial —, a ficha exibe um chip vermelho de
  // erro no lugar do valor. Nunca cai em "—", que sugeriria "não preencheu".
  const estadoValor: React.ReactNode = ufpa.municipio.estado ? (
    ufpa.municipio.estado.nome
  ) : (
    <span
      className="inline-flex items-center rounded-full border border-error-text bg-error-bg px-2 py-0.5 text-2xs font-semibold text-error-text"
      role="alert"
    >
      Localização incompleta — contate o suporte
    </span>
  );

  return [
    {
      id: "localizacao",
      label: "Localização",
      content: (
        <DefinitionList
          items={[
            { label: "Estado", value: estadoValor },
            { label: "Município", value: ufpa.municipio.nome },
            { label: "Comunidade", value: ufpa.comunidade?.nome },
            { label: "Território", value: ufpa.territorio?.nome },
            { label: "GPS", value: gps(ufpa) },
            { label: "Endereço", value: joinAddress(ufpa) },
            { label: "CEP", value: formatCep(ufpa.cep) },
            { label: "Projeto", value: ufpa.projeto.nome },
          ]}
        />
      ),
    },
    {
      id: "dados-basicos",
      label: "Dados Básicos",
      content: (
        <DefinitionList
          items={[
            { label: "Titular", value: ufpa.titular.nome_completo },
            { label: "CPF", value: maskCpf(ufpa.titular.cpf) },
            { label: "Apelido", value: ufpa.apelido },
            { label: "RG", value: ufpa.titular.rg },
            { label: "Nascimento", value: formatDate(ufpa.titular.data_nascimento) },
            { label: "Gênero", value: ufpa.titular.genero_display },
            // Cor/Raça é sensível (#192): quando o backend omite a chave por
            // falta de permissão, a linha não entra na lista — nada de "—".
            ...("cor_raca_display" in ufpa.titular
              ? [{ label: "Cor/Raça", value: ufpa.titular.cor_raca_display }]
              : []),
            { label: "PCT", value: labelForValue(choices.pct, ufpa.pct) },
            { label: "NIS", value: ufpa.titular.nis },
            { label: "DAP/CAF", value: ufpa.dap_caf },
            { label: "Escolaridade", value: ufpa.titular.escolaridade_display },
            { label: "Seguridade", value: seguridade },
            {
              label: "Posse da terra",
              value: labelForValue(choices.posse_terra, ufpa.posse_terra),
            },
            { label: "Área", value: formatArea(ufpa.area_terra_ha) },
          ]}
        />
      ),
    },
    {
      id: "comunicacao",
      label: "Comunicação",
      content: (
        <DefinitionList
          items={[
            { label: "Telefone", value: formatPhone(ufpa.celular) },
            { label: "WhatsApp", value: formatPhone(ufpa.whatsapp) },
            { label: "Internet", value: formatBool(ufpa.internet) },
            {
              label: "Dispositivo",
              value: labelForValue(choices.dispositivo, ufpa.dispositivo),
            },
          ]}
        />
      ),
    },
    {
      id: "moradia",
      label: "Moradia",
      content: (
        <DefinitionList
          items={[
            {
              label: "Tipo",
              value: labelForValue(choices.tipo_moradia, ufpa.tipo_moradia),
            },
            {
              label: "Material",
              value: labelForValue(
                choices.material_construcao,
                ufpa.material_construcao,
              ),
            },
            {
              label: "Cômodos",
              value:
                ufpa.num_comodos !== null && ufpa.num_comodos !== undefined
                  ? String(ufpa.num_comodos)
                  : undefined,
            },
            {
              label: "Energia",
              value: labelForValue(choices.energia, ufpa.energia),
            },
            { label: "Água", value: labelForValue(choices.agua, ufpa.agua) },
            {
              label: "Situação",
              value: labelForValue(choices.situacao_moradia, ufpa.situacao_moradia),
            },
          ]}
        />
      ),
    },
    {
      id: "membros",
      label: "Membros",
      content: <MembrosTab ufpaId={String(ufpa.id)} />,
    },
    {
      id: "producao",
      label: "Produção",
      content: <ProducaoTab ufpaId={String(ufpa.id)} />,
    },
    {
      id: "documentos",
      label: "Documentos",
      content: <DocumentosTab ufpaId={String(ufpa.id)} />,
    },
    {
      id: "formularios",
      label: "Formulários",
      content: <FormulariosTab ufpaId={String(ufpa.id)} />,
    },
    {
      id: "historico",
      label: "Histórico",
      content: <HistoricoTab ufpaId={String(ufpa.id)} />,
    },
  ];
}

export default function UfpaDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const [status, setStatus] = useState<Status>("loading");
  const [ufpa, setUfpa] = useState<UfpaDetail | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const rawTab = searchParams.get("tab") ?? "";
  const tab: TabId = (TAB_IDS as readonly string[]).includes(rawTab)
    ? (rawTab as TabId)
    : "localizacao";

  /**
   * Trocar de aba é ação do usuário — usa `router.push` para o Voltar do
   * browser percorrer as abas visitadas. Parte de uma cópia dos `searchParams`
   * para não descartar outros params (ex.: filtros da aba Formulários) ao
   * reescrever a URL.
   */
  const setTab = (id: string) => {
    const next = new URLSearchParams(searchParams.toString());
    next.set("tab", id);
    router.push(`${pathname}?${next.toString()}`, { scroll: false });
  };

  /**
   * Compatibilidade com URLs antigas: quando a página abre sem `?tab=` mas com
   * um hash de aba válido (`#membros`, `#producao`, …), converte para
   * `?tab=<id>` via `router.replace` — não polui o histórico e mantém quem já
   * tinha o link salvo aterrizando na aba correta.
   */
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (searchParams.get("tab")) return;
    const hash = window.location.hash.replace(/^#/, "");
    if (!(TAB_IDS as readonly string[]).includes(hash)) return;
    const next = new URLSearchParams(searchParams.toString());
    next.set("tab", hash);
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }, [searchParams, router, pathname]);

  useEffect(() => {
    // Protege contra ids não numéricos (ex.: colisão com /sgp/ufpas/nova/).
    if (!/^\d+$/.test(id)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStatus("notfound");
      return;
    }

    const controller = new AbortController();
    setStatus("loading");

    getUfpaDetail(id, controller.signal)
      .then((data) => {
        setUfpa(data);
        setStatus("ok");
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 404) setStatus("notfound");
        else if (e instanceof ApiError && e.status === 403)
          setStatus("forbidden");
        else setStatus("error");
      });

    return () => controller.abort();
  }, [id, reloadKey]);

  const choices = useSgpChoices();
  const tabs = useMemo(
    () => (ufpa ? buildTabs(ufpa, choices) : []),
    [ufpa, choices],
  );

  function handlePhotoChange(url: string | null) {
    setUfpa((prev) => (prev ? { ...prev, foto_url: url ?? "" } : prev));
  }

  if (status === "notfound") {
    notFound();
  }

  if (status === "forbidden") {
    return (
      <>
        <PageHeader>
          <span className="truncate text-base font-semibold text-text">
            UFPAs
          </span>
        </PageHeader>
        <RestrictedAccess />
      </>
    );
  }

  if (status === "loading") {
    return (
      <>
        <PageHeader>
          <span className="truncate text-base font-semibold text-text">
            UFPAs
          </span>
        </PageHeader>
        <UfpaDetailSkeleton />
      </>
    );
  }

  if (status === "error" || !ufpa) {
    return (
      <>
        <PageHeader>
          <span className="truncate text-base font-semibold text-text">
            UFPAs
          </span>
        </PageHeader>
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <p className="max-w-sm text-sm text-text-muted">
            Não foi possível carregar a UFPA. Tente novamente.
          </p>
          <Button
            variant="secondary"
            onClick={() => setReloadKey((k) => k + 1)}
          >
            Tentar novamente
          </Button>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">UFPAs</span>
      </PageHeader>

      <div className="mx-auto max-w-5xl space-y-6">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "UFPAs", href: "/sgp/ufpas" },
            { label: ufpa.titular.nome_completo },
          ]}
        />

        <UfpaHeader ufpa={ufpa} onPhotoChange={handlePhotoChange} />

        <Tabs
          items={tabs}
          value={tab}
          onValueChange={setTab}
          aria-label="Seções da UFPA"
        />
      </div>
    </>
  );
}
