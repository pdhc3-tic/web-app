"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import Spinner from "@/app/components/icons/Spinner";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { useCanReviewSyncConflicts } from "@/app/lib/auth/roles";
import { absoluteDateTime, relativeTime } from "@/app/lib/datetime";
import {
  ENTIDADE_LABEL,
  ESTRATEGIA_LABEL,
  fetchConflito,
  formatarValor,
  resolverConflito,
  rotuloCampo,
  type ConflitoDecisao,
  type ConflitoDetalhe,
  type ValorConflito,
} from "@/app/lib/conflitos";
import { ConfrontoValores } from "../_components/ConfrontoValores";
import { SensivelBadge, StatusConflitoBadge } from "../_components/ConflitoBadges";
import { RegistroAtual } from "./_components/RegistroAtual";
import { ResolucaoForm } from "./_components/ResolucaoForm";

function CenteredSpinner() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="h-6 w-6 animate-spin text-text-muted" />
    </div>
  );
}

export default function ConflitoDetalhePage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();
  const { showToast } = useToast();
  const { loading: authLoading, canReview } = useCanReviewSyncConflicts();

  const [conflito, setConflito] = useState<ConflitoDetalhe | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [naoEncontrado, setNaoEncontrado] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [salvando, setSalvando] = useState(false);
  const [erroResolucao, setErroResolucao] = useState<string | null>(null);

  useEffect(() => {
    if (!canReview || !Number.isInteger(id)) return;

    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setLoadError(null);

    fetchConflito(id, controller.signal)
      .then(setConflito)
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 403) {
          setForbidden(true);
          return;
        }
        if (e instanceof ApiError && e.status === 404) {
          // Fora do escopo territorial o queryset simplesmente não devolve o
          // registro — para quem não pode vê-lo, ele não existe.
          setNaoEncontrado(true);
          return;
        }
        setLoadError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar o conflito. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [canReview, id, reloadKey]);

  const handleResolver = useCallback(
    async (decisao: ConflitoDecisao, valorManual?: ValorConflito) => {
      if (salvando) return;
      setSalvando(true);
      setErroResolucao(null);

      try {
        await resolverConflito(id, decisao, valorManual);
        showToast("Conflito resolvido.", "success");
        router.push("/sca/conflitos");
      } catch (e: unknown) {
        if (e instanceof ApiError && e.status === 409) {
          setErroResolucao(
            "Este conflito já foi resolvido por outra pessoa. Recarregue para ver a decisão registrada.",
          );
        } else if (e instanceof ApiError) {
          setErroResolucao(e.message);
        } else {
          setErroResolucao(
            "Não foi possível registrar a resolução. Tente novamente.",
          );
        }
        setSalvando(false);
      }
      // Sem `finally`: no sucesso a navegação desmonta a tela, e desligar o
      // "salvando" aqui devolveria o botão ao normal por um instante.
    },
    [id, salvando, showToast, router],
  );

  const header = (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">
        Conflito de sincronização
      </h1>
    </PageHeader>
  );

  if (authLoading) {
    return (
      <>
        {header}
        <CenteredSpinner />
      </>
    );
  }

  if (!canReview || forbidden) {
    return (
      <>
        {header}
        <RestrictedAccess />
      </>
    );
  }

  if (loading && !conflito) {
    return (
      <>
        {header}
        <CenteredSpinner />
      </>
    );
  }

  if (naoEncontrado || (!conflito && !loadError)) {
    return (
      <>
        {header}
        <Aviso
          mensagem="Conflito não encontrado. Ele pode ter sido removido ou estar fora dos territórios sob sua responsabilidade."
          acao={
            <Button as="a" href="/sca/conflitos" variant="secondary">
              Voltar para a lista
            </Button>
          }
        />
      </>
    );
  }

  if (loadError || !conflito) {
    return (
      <>
        {header}
        <Aviso
          mensagem={loadError ?? "Não foi possível carregar o conflito."}
          acao={
            <Button
              variant="secondary"
              onClick={() => setReloadKey((k) => k + 1)}
            >
              Tentar novamente
            </Button>
          }
        />
      </>
    );
  }

  const pendente = conflito.status === "pendente";

  return (
    <div data-testid="conflito-detalhe-page" data-status={conflito.status}>
      {header}

      <div className="mx-auto flex max-w-3xl flex-col gap-5">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "Conflitos de sincronização", href: "/sca/conflitos" },
            { label: rotuloCampo(conflito.campo) },
          ]}
        />

        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-semibold tracking-tight text-text">
              {rotuloCampo(conflito.campo)}
            </h2>
            {conflito.campo_sensivel && <SensivelBadge />}
            <StatusConflitoBadge status={conflito.status} />
          </div>
          <p className="text-sm text-text-muted">
            {ENTIDADE_LABEL[conflito.entidade] ?? conflito.entidade} · detectado{" "}
            <span title={absoluteDateTime(conflito.criado_em)}>
              {relativeTime(conflito.criado_em)}
            </span>
          </p>
        </div>

        <section className="rounded-lg border border-border bg-surface p-6">
          <DefinitionList
            items={[
              { label: "Território", value: conflito.territorio?.nome ?? "—" },
              { label: "Coletado por", value: conflito.tecnico.nome },
              {
                label: "Dispositivo",
                value: conflito.dispositivo
                  ? `${conflito.dispositivo.nome} (${conflito.dispositivo.device_id})`
                  : "—",
              },
              {
                label: "Estratégia aplicada",
                value:
                  ESTRATEGIA_LABEL[conflito.estrategia] ?? conflito.estrategia,
              },
            ]}
          />
        </section>

        {pendente ? (
          <ResolucaoForm
            conflito={conflito}
            salvando={salvando}
            erro={erroResolucao}
            onResolver={handleResolver}
          />
        ) : (
          <section
            data-testid="conflito-resolvido"
            className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-6"
          >
            <div className="flex flex-col gap-1">
              <h2 className="text-sm font-medium text-text">
                Conflito já resolvido
              </h2>
              <p className="text-sm text-text-muted">
                {conflito.status === "resolvido_auto"
                  ? "O sistema resolveu automaticamente — campos não sensíveis seguem a regra de última escrita."
                  : "A decisão foi tomada manualmente e já está aplicada ao registro."}
              </p>
            </div>

            <ConfrontoValores
              valorLocal={conflito.valor_local}
              valorServidor={conflito.valor_servidor}
            />

            <DefinitionList
              items={[
                {
                  label: "Valor aplicado",
                  value: formatarValor(conflito.valor_final),
                },
                {
                  label: "Resolvido por",
                  value: conflito.resolvido_por?.nome ?? "Sistema",
                },
                {
                  label: "Resolvido em",
                  value: conflito.resolvido_em
                    ? absoluteDateTime(conflito.resolvido_em)
                    : "—",
                },
              ]}
            />
          </section>
        )}

        <RegistroAtual registro={conflito.registro_atual} />
      </div>
    </div>
  );
}

function Aviso({
  mensagem,
  acao,
}: {
  mensagem: string;
  acao: React.ReactNode;
}) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
        <AlertTriangle className="h-6 w-6" aria-hidden />
      </span>
      <p className="max-w-sm text-sm text-text-muted">{mensagem}</p>
      {acao}
    </div>
  );
}
