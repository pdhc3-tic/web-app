"use client";

import { useEffect, useState } from "react";
import { notFound, useParams } from "next/navigation";
import { AlertTriangle, MapPin, Pencil, User, Users } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import Spinner from "@/app/components/icons/Spinner";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { OrigemScaBadge } from "@/app/components/sgp/OrigemScaBadge";
import { ApiError } from "@/app/lib/api";
import {
  badgeStatusFor,
  getAtividade,
  statusLabel,
  type AtividadeDetail,
} from "@/app/lib/atividades";
import { formatDate, formatTimeRange } from "@/app/lib/datetime";

type Status = "loading" | "ok" | "notfound" | "forbidden" | "error";

function HeaderSlot() {
  return (
    <PageHeader>
      <span className="truncate text-base font-semibold text-text">
        Atividades
      </span>
    </PageHeader>
  );
}

/**
 * Ficha da Atividade — leitura.
 *
 * Até aqui a lista levava direto ao formulário de edição, e o painel do
 * calendário oferecia "abrir ficha completa" apontando para o mesmo formulário.
 * Ver uma atividade exigia entrar no modo de edição dela, o que é desconfortável
 * para quem só quer consultar — e impossível para quem não tem permissão de
 * escrita.
 */
export default function AtividadeFichaPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [status, setStatus] = useState<Status>("loading");
  const [atividade, setAtividade] = useState<AtividadeDetail | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!/^\d+$/.test(id)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStatus("notfound");
      return;
    }
    const controller = new AbortController();
    setStatus("loading");

    getAtividade(id, controller.signal)
      .then((data) => {
        setAtividade(data);
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

  if (status === "notfound") {
    notFound();
  }

  if (status === "forbidden") {
    return (
      <>
        <HeaderSlot />
        <RestrictedAccess />
      </>
    );
  }

  if (status === "loading" || !atividade) {
    if (status === "error") {
      return (
        <>
          <HeaderSlot />
          <div className="mx-auto flex min-h-[40vh] max-w-4xl flex-col items-center justify-center gap-4 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" aria-hidden />
            </span>
            <p className="max-w-sm text-sm text-text-muted">
              Não foi possível carregar a atividade. Tente novamente.
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
        <HeaderSlot />
        <div
          role="status"
          className="mx-auto flex min-h-[40vh] max-w-4xl items-center justify-center gap-2 text-sm text-text-muted"
        >
          <Spinner className="h-5 w-5 animate-spin" />
          Carregando atividade…
        </div>
      </>
    );
  }

  const periodo =
    atividade.data_inicio === atividade.data_fim
      ? formatDate(atividade.data_inicio)
      : `${formatDate(atividade.data_inicio)} — ${formatDate(atividade.data_fim)}`;

  return (
    <>
      <HeaderSlot />

      <div
        data-testid="atividade-ficha-page"
        className="mx-auto flex max-w-4xl flex-col gap-6"
      >
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGP", href: "/sgp" },
            { label: "Atividades", href: "/sgp/atividades" },
            { label: atividade.titulo },
          ]}
        />

        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-semibold tracking-tight text-text">
              {atividade.titulo}
            </h1>
            <p className="mt-1 text-sm text-text-muted">
              {atividade.tipo_atividade_display} · {periodo}
              {formatTimeRange(atividade.data_inicio, atividade.data_fim)
                ? ` · ${formatTimeRange(atividade.data_inicio, atividade.data_fim)}`
                : ""}
            </p>

            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge
                status={badgeStatusFor(atividade.status)}
                label={atividade.status_display || statusLabel(atividade.status)}
              />
              {atividade.atrasada && (
                <Badge status="atrasada" label="Atrasada" />
              )}
              <OrigemScaBadge registro={atividade} />
            </div>
          </div>

          <div className="shrink-0">
            <Button
              as="a"
              href={`/sgp/atividades/${atividade.id}/editar/`}
              variant="secondary"
              size="sm"
              leftIcon={<Pencil className="h-4 w-4" />}
              data-testid="atividade-editar-btn"
            >
              Editar
            </Button>
          </div>
        </div>

        <section className="rounded-lg border border-border bg-surface p-6">
          <h2 className="mb-4 text-sm font-medium text-text">
            Vínculo com o Plano de Trabalho
          </h2>
          <DefinitionList
            items={[
              {
                label: "Ação",
                value: `${atividade.acao.numero} — ${atividade.acao.descricao}`,
              },
              { label: "Âmbito", value: atividade.ambito_display },
              {
                label: "Forma de atuação",
                value: atividade.forma_atuacao_display,
              },
            ]}
          />
        </section>

        <section className="rounded-lg border border-border bg-surface p-6">
          <h2 className="mb-4 text-sm font-medium text-text">
            Equipe e local
          </h2>
          <DefinitionList
            items={[
              {
                label: "Técnico responsável",
                value: (
                  <span className="inline-flex items-center gap-1.5">
                    <User className="h-3.5 w-3.5 text-text-muted" aria-hidden />
                    {atividade.tecnico_responsavel.nome}
                  </span>
                ),
              },
              {
                label: "Local",
                value: (
                  <span className="inline-flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5 text-text-muted" aria-hidden />
                    {atividade.comunidade
                      ? `${atividade.municipio.nome} · ${atividade.comunidade.nome}`
                      : atividade.municipio.nome}
                  </span>
                ),
              },
              {
                label: "Participantes",
                value: (
                  <span className="inline-flex items-center gap-1.5">
                    <Users className="h-3.5 w-3.5 text-text-muted" aria-hidden />
                    {atividade.total_participantes}
                  </span>
                ),
              },
              { label: "Parceiros", value: atividade.parceiros },
            ]}
          />
        </section>

        {(atividade.descricao_narrativa ||
          atividade.resultados_alcancados ||
          atividade.justificativa) && (
          <section className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-6">
            <h2 className="text-sm font-medium text-text">Registro</h2>

            <Texto titulo="Descrição" conteudo={atividade.descricao_narrativa} />
            <Texto
              titulo="Resultados alcançados"
              conteudo={atividade.resultados_alcancados}
            />
            <Texto titulo="Justificativa" conteudo={atividade.justificativa} />
          </section>
        )}

        {!atividade.ativo && (
          <p className="flex items-center gap-2 text-sm text-text-muted">
            <Chip>Excluída</Chip>
            Esta atividade foi removida e está visível apenas para consulta.
          </p>
        )}
      </div>
    </>
  );
}

function Texto({ titulo, conteudo }: { titulo: string; conteudo: string }) {
  if (!conteudo?.trim()) return null;
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-2xs uppercase tracking-[0.08em] text-text-muted">
        {titulo}
      </h3>
      <p className="whitespace-pre-wrap text-sm text-text">{conteudo}</p>
    </div>
  );
}
