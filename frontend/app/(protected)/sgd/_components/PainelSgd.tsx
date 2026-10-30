"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { AlertTriangle, ChevronRight, Clock, Inbox, PauseCircle } from "lucide-react";
import type { ReactNode } from "react";
import Spinner from "@/app/components/icons/Spinner";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Button } from "@/app/components/ui/Button/Button";
import { SemaforoBadge } from "@/app/components/ui/SemaforoBadge/SemaforoBadge";
import { canViewSgdGestao } from "@/app/lib/auth/roles";
import { badgeStatusDaDemanda } from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import {
  faixaDeEspera,
  fetchSgdDashboard,
  linkDaFila,
  linkDaParada,
  linkDoAlerta,
  rotuloDeEspera,
  type AlertaSaldo,
  type ItemFila,
  type ItemParado,
  type SgdDashboard,
} from "@/app/lib/sgdDashboard";
import { useRotuloChoice } from "@/app/providers/SgpChoicesProvider";

const formatoPercentual = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

/**
 * Home do SGD (#318): fila "Aguardando minha ação", alertas de saldo por
 * rubrica, demandas paradas e contadores — tudo de `GET /sgd/dashboard/`
 * (BE-11), já no recorte do perfil logado.
 */
export function PainelSgd() {
  const painel = useQuery({
    queryKey: qk.demandas.dashboard,
    queryFn: ({ signal }) => fetchSgdDashboard(signal),
    staleTime: 30_000,
  });

  if (painel.isPending) {
    return (
      <div
        role="status"
        className="flex min-h-[20vh] items-center justify-center gap-2 rounded-lg border border-border bg-surface text-sm text-text-muted"
        data-testid="painel-sgd-carregando"
      >
        <Spinner className="h-5 w-5 animate-spin" />
        Carregando o painel…
      </div>
    );
  }

  if (painel.isError) {
    return (
      <div
        role="alert"
        className="flex flex-col items-center gap-3 rounded-lg border border-border bg-surface px-6 py-10 text-center"
        data-testid="painel-sgd-erro"
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-error-bg text-error-text">
          <AlertTriangle className="h-5 w-5" aria-hidden />
        </span>
        <p className="max-w-sm text-sm text-text-muted">Não foi possível carregar o painel do SGD.</p>
        <Button variant="secondary" onClick={() => void painel.refetch()}>
          Tentar novamente
        </Button>
      </div>
    );
  }

  return <Conteudo dados={painel.data} />;
}

function Conteudo({ dados }: { dados: SgdDashboard }) {
  const { data: session } = useSession();
  const podeVerExecucao = canViewSgdGestao(session?.user);

  return (
    <div className="flex flex-col gap-6" data-testid="painel-sgd">
      {dados.contagem_por_status.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Demandas por status" data-testid="painel-contadores">
          {dados.contagem_por_status.map((c) => (
            <li
              key={c.status}
              className="flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-sm"
              data-testid={`contador-${c.status}`}
            >
              <span className="text-text-muted">{c.rotulo}</span>
              <span className="font-semibold tabular-nums text-text">{c.total}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Secao
          titulo="Aguardando minha ação"
          total={dados.fila_aguardando_acao.total}
          testId="painel-fila"
          vazio={{
            icon: <Inbox className="h-6 w-6" />,
            titulo: "Nenhuma demanda aguardando você",
            descricao: "Quando uma demanda chegar à sua etapa, ela aparece aqui.",
          }}
        >
          {dados.fila_aguardando_acao.itens.length > 0 && (
            <ul className="divide-y divide-border">
              {dados.fila_aguardando_acao.itens.map((item) => (
                <LinhaFila key={item.id} item={item} />
              ))}
            </ul>
          )}
          {dados.fila_aguardando_acao.total > dados.fila_aguardando_acao.itens.length && (
            <Rodape href="/sgd/demandas">Ver a fila completa no painel de demandas</Rodape>
          )}
        </Secao>

        <div className="flex flex-col gap-6">
          <Secao
            titulo="Alertas de saldo"
            total={dados.alertas_saldo.length}
            testId="painel-alertas"
            vazio={{
              icon: <AlertTriangle className="h-6 w-6" />,
              titulo: "Nenhuma rubrica em alerta",
              descricao: "As rubricas do seu escopo estão abaixo da faixa amarela.",
            }}
          >
            {dados.alertas_saldo.length > 0 && (
              <ul className="flex flex-col gap-2 p-3">
                {dados.alertas_saldo.map((alerta) => (
                  <CartaoAlerta
                    key={`${alerta.meta_id}-${alerta.rubrica_id}-${alerta.estado_sigla ?? ""}-${alerta.territorio_id ?? ""}`}
                    alerta={alerta}
                    href={linkDoAlerta(alerta, podeVerExecucao)}
                  />
                ))}
              </ul>
            )}
          </Secao>

          <Secao
            titulo="Sem movimentação há 5 dias úteis"
            total={dados.sem_movimentacao.total}
            testId="painel-paradas"
            vazio={{
              icon: <PauseCircle className="h-6 w-6" />,
              titulo: "Nenhuma demanda parada",
              descricao: "Nada sob a sua responsabilidade está sem movimentação.",
            }}
          >
            {dados.sem_movimentacao.itens.length > 0 && (
              <ul className="divide-y divide-border">
                {dados.sem_movimentacao.itens.map((item) => (
                  <LinhaParada key={item.id} item={item} />
                ))}
              </ul>
            )}
          </Secao>
        </div>
      </div>
    </div>
  );
}

function Secao({
  titulo,
  total,
  testId,
  vazio,
  children,
}: {
  titulo: string;
  total: number;
  testId: string;
  vazio: { icon: ReactNode; titulo: string; descricao: string };
  children: ReactNode;
}) {
  return (
    <section
      className="flex min-w-0 flex-col rounded-lg border border-border bg-surface"
      aria-label={titulo}
      data-testid={testId}
    >
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-text">{titulo}</h2>
        <span className="text-xs tabular-nums text-text-muted" data-testid={`${testId}-total`}>
          {total}
        </span>
      </header>
      {total === 0 ? (
        <div className="flex flex-col items-center gap-2 px-6 py-8 text-center" data-testid={`${testId}-vazio`}>
          <span
            aria-hidden
            className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-muted text-text-muted"
          >
            {vazio.icon}
          </span>
          <p className="text-sm font-medium text-text">{vazio.titulo}</p>
          <p className="max-w-xs text-xs text-text-muted">{vazio.descricao}</p>
        </div>
      ) : (
        children
      )}
    </section>
  );
}

function Rodape({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="flex items-center justify-center gap-1 border-t border-border px-4 py-2.5 text-sm text-primary hover:underline"
    >
      {children}
      <ChevronRight className="h-4 w-4" aria-hidden />
    </Link>
  );
}

function LinhaFila({ item }: { item: ItemFila }) {
  const statusLabel = useRotuloChoice("demanda_status");
  const local = [item.territorio, item.estado].filter(Boolean).join(" · ");
  return (
    <li data-testid={`fila-item-${item.id}`}>
      <Link
        href={linkDaFila(item.id)}
        className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-surface-muted"
      >
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="truncate text-sm font-medium text-text">{item.titulo}</span>
          <span className="truncate text-xs text-text-muted">
            {item.atividade_titulo}
            {local && ` · ${local}`}
          </span>
          <span className="flex flex-wrap items-center gap-2">
            <Badge status={badgeStatusDaDemanda(item.status)} label={statusLabel(item.status)} />
            <span className="text-xs tabular-nums text-text">{formatCurrencyBRL(item.valor_estimado)}</span>
          </span>
        </div>
        <span className="flex shrink-0 items-center gap-1" data-testid={`fila-espera-${item.id}`}>
          <Clock className="h-3.5 w-3.5 text-text-muted" aria-hidden />
          <SemaforoBadge nivel={faixaDeEspera(item.dias_em_espera)} label={rotuloDeEspera(item.dias_em_espera)} />
        </span>
      </Link>
    </li>
  );
}

function CartaoAlerta({ alerta, href }: { alerta: AlertaSaldo; href: string }) {
  const local = alerta.estado_sigla ?? (alerta.nivel === "nacional" ? "Nacional" : null);
  return (
    <li data-testid={`alerta-${alerta.rubrica_slug}-${alerta.meta_id}-${alerta.estado_sigla ?? alerta.territorio_id ?? "nacional"}`}>
      <Link
        href={href}
        className="flex flex-col gap-1.5 rounded-md border border-border px-3 py-2.5 transition-colors hover:bg-surface-muted"
      >
        <span className="flex items-start justify-between gap-2">
          <span className="min-w-0 text-sm font-medium text-text">{alerta.rubrica_nome}</span>
          <SemaforoBadge
            nivel={alerta.faixa}
            label={`${formatoPercentual.format(Number(alerta.percentual_comprometido))}% comprometido`}
          />
        </span>
        <span className="text-xs text-text-muted">
          Meta {alerta.meta_numero}
          {local && ` · ${local}`} · saldo {formatCurrencyBRL(alerta.saldo_disponivel)} de{" "}
          {formatCurrencyBRL(alerta.valor_aprovado)}
        </span>
      </Link>
    </li>
  );
}

function LinhaParada({ item }: { item: ItemParado }) {
  const statusLabel = useRotuloChoice("demanda_status");
  return (
    <li data-testid={`parada-item-${item.id}`}>
      <Link
        href={linkDaParada(item.id)}
        className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-muted"
      >
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="truncate text-sm font-medium text-text">{item.titulo}</span>
          <span className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
            <Badge status={badgeStatusDaDemanda(item.status)} label={statusLabel(item.status)} />
            {item.estado}
          </span>
        </div>
        <span className="shrink-0 text-xs font-medium tabular-nums text-warning-text">
          {item.dias_uteis_parada} dias úteis
        </span>
      </Link>
    </li>
  );
}
