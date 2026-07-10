"use client";

import { useEffect, useMemo, useState } from "react";
import { notFound, useParams } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { Tabs, type TabItem } from "@/app/components/ui/Tabs/Tabs";
import { ApiError } from "@/app/lib/api";
import { getUpfDetail, type UpfDetail } from "@/app/lib/upfs";
import { formatDate } from "@/app/lib/datetime";
import {
  formatArea,
  formatBool,
  formatCep,
  formatPhone,
  maskCpf,
} from "@/app/lib/format";
import { UpfHeader } from "./_components/UpfHeader";
import { UpfDetailSkeleton } from "./_components/UpfDetailSkeleton";
import { HistoricoTab } from "./_components/HistoricoTab";
import { MembrosTab } from "./_components/MembrosTab";

const TAB_IDS = [
  "localizacao",
  "dados-basicos",
  "comunicacao",
  "moradia",
  "membros",
  "historico",
] as const;
type TabId = (typeof TAB_IDS)[number];

type Status = "loading" | "ok" | "notfound" | "forbidden" | "error";

/** Aba ativa espelhada no hash da URL (ex.: #moradia). */
function useHashTab(): [TabId, (id: string) => void] {
  const [tab, setTab] = useState<TabId>("localizacao");

  useEffect(() => {
    const read = () => {
      const hash = window.location.hash.replace(/^#/, "");
      setTab(
        (TAB_IDS as readonly string[]).includes(hash)
          ? (hash as TabId)
          : "localizacao",
      );
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);

  const change = (id: string) => {
    history.replaceState(null, "", `#${id}`);
    setTab(id as TabId);
  };

  return [tab, change];
}

function joinAddress(upf: UpfDetail): string {
  const line = [upf.logradouro, upf.numero].filter(Boolean).join(", ");
  return [line, upf.complemento, upf.bairro].filter(Boolean).join(" · ");
}

function gps(upf: UpfDetail): string {
  return upf.latitude && upf.longitude
    ? `${upf.latitude}, ${upf.longitude}`
    : "";
}

function buildTabs(upf: UpfDetail): TabItem[] {
  const seguridade =
    upf.seguridade_social.length > 0 ? (
      <div className="flex flex-wrap gap-1.5">
        {upf.seguridade_social.map((s) => (
          <Chip key={s}>{s}</Chip>
        ))}
      </div>
    ) : undefined;

  return [
    {
      id: "localizacao",
      label: "Localização",
      content: (
        <DefinitionList
          items={[
            { label: "Estado", value: undefined },
            { label: "Município", value: upf.municipio.nome },
            { label: "Comunidade", value: upf.comunidade?.nome },
            { label: "Território", value: upf.territorio?.nome },
            { label: "GPS", value: gps(upf) },
            { label: "Endereço", value: joinAddress(upf) },
            { label: "CEP", value: formatCep(upf.cep) },
            { label: "Projeto", value: upf.projeto.nome },
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
            { label: "Titular", value: upf.nome_titular },
            { label: "CPF", value: maskCpf(upf.cpf) },
            { label: "Apelido", value: upf.apelido },
            { label: "RG", value: upf.rg },
            { label: "Nascimento", value: formatDate(upf.data_nasc) },
            { label: "Gênero", value: upf.genero },
            { label: "Cor/Raça", value: upf.cor_raca },
            { label: "PCT", value: upf.pct },
            { label: "NIS", value: upf.nis },
            { label: "DAP/CAF", value: upf.daf_caf },
            { label: "Estado civil", value: upf.estado_civil },
            { label: "Escolaridade", value: upf.escolaridade },
            { label: "Seguridade", value: seguridade },
            { label: "Posse da terra", value: upf.posse_terra },
            { label: "Área", value: formatArea(upf.area_terra_ha) },
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
            {
              label: "Telefone",
              value: formatPhone(upf.telefone || upf.celular),
            },
            { label: "WhatsApp", value: formatPhone(upf.whatsapp) },
            { label: "E-mail", value: upf.email },
            { label: "Internet", value: formatBool(upf.internet) },
            { label: "Dispositivo", value: upf.dispositivo },
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
            { label: "Tipo", value: upf.tipo_moradia },
            { label: "Material", value: undefined },
            { label: "Cômodos", value: undefined },
            { label: "Energia", value: upf.energia },
            { label: "Água", value: upf.agua },
            { label: "Situação", value: upf.situacao_moradia },
          ]}
        />
      ),
    },
    {
      id: "membros",
      label: "Membros",
      content: <MembrosTab upfId={String(upf.id)} />,
    },
    {
      id: "historico",
      label: "Histórico",
      content: <HistoricoTab upfId={String(upf.id)} />,
    },
  ];
}

export default function UpfDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [status, setStatus] = useState<Status>("loading");
  const [upf, setUpf] = useState<UpfDetail | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [tab, setTab] = useHashTab();

  useEffect(() => {
    // Protege contra ids não numéricos (ex.: colisão com /sgp/upfs/nova/).
    if (!/^\d+$/.test(id)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStatus("notfound");
      return;
    }

    const controller = new AbortController();
    setStatus("loading");

    getUpfDetail(id, controller.signal)
      .then((data) => {
        setUpf(data);
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

  const tabs = useMemo(() => (upf ? buildTabs(upf) : []), [upf]);

  if (status === "notfound") {
    notFound();
  }

  if (status === "forbidden") {
    return (
      <>
        <PageHeader>
          <span className="truncate text-base font-semibold text-text">
            UPFs
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
            UPFs
          </span>
        </PageHeader>
        <UpfDetailSkeleton />
      </>
    );
  }

  if (status === "error" || !upf) {
    return (
      <>
        <PageHeader>
          <span className="truncate text-base font-semibold text-text">
            UPFs
          </span>
        </PageHeader>
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <p className="max-w-sm text-sm text-text-muted">
            Não foi possível carregar a UPF. Tente novamente.
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
        <span className="truncate text-base font-semibold text-text">UPFs</span>
      </PageHeader>

      <div className="mx-auto max-w-5xl space-y-6">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "UPFs", href: "/sgp/upfs" },
            { label: upf.nome_titular },
          ]}
        />

        <UpfHeader upf={upf} />

        <Tabs
          items={tabs}
          value={tab}
          onValueChange={setTab}
          aria-label="Seções da UPF"
        />
      </div>
    </>
  );
}
