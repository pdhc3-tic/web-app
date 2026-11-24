"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import type { Route } from "next";
import { ChevronRight, Gauge, ListTree, SlidersHorizontal, TableProperties } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import Spinner from "@/app/components/icons/Spinner";
import { useIsSuperAdmin } from "@/app/lib/auth/roles";
import { hojeIso, lacunasDeValor, listarFaixas, listarValores } from "@/app/lib/diarias";
import { qk } from "@/app/lib/queryKeys";

type Configuracao = { href: Route; titulo: string; descricao: string; Icon: LucideIcon };

/**
 * Configurações do sistema, por módulo (#319). Só Super Admin, o mesmo gate
 * das telas filhas. Nova configuração = novo item na seção do módulo.
 */
const SECOES: { modulo: string; itens: Configuracao[] }[] = [
  {
    modulo: "SGP",
    itens: [
      {
        href: "/admin/configuracoes/sgp/parametros-orcamento" as Route,
        titulo: "Parâmetros do orçamento",
        descricao:
          "Periodicidade e acúmulo dos limites de gasto, sobrealocação e os limiares dos alertas de subexecução e de remanejamento.",
        Icon: Gauge,
      },
    ],
  },
  {
    modulo: "SGD",
    itens: [
      {
        href: "/admin/configuracoes/sgd/tipos-rubricas" as Route,
        titulo: "Tipos de solicitação",
        descricao:
          "Os tipos que o solicitante escolhe, a rubrica de cada um e os campos do formulário (diárias, passagens, veículos…).",
        Icon: ListTree,
      },
      {
        href: "/admin/configuracoes/sgd/diarias" as Route,
        titulo: "Tabela de diárias",
        descricao:
          "Valor da diária por faixa de destino e vigência, os municípios de cada faixa e as regras de meia diária e do adicional de embarque.",
        Icon: TableProperties,
      },
      {
        href: "/admin/configuracoes/sgd/integracao-arlo" as Route,
        titulo: "Integração Arlo",
        descricao: "Quais campos do SGD saem no CSV enviado ao Arlo, em que ordem, e como o retorno é lido.",
        Icon: SlidersHorizontal,
      },
    ],
  },
];

/**
 * Aviso no card da Tabela de diárias (#440): faixa ativa sem valor vigente faz
 * o SGD recusar toda diária para os municípios dela, e o Super Admin só
 * descobriria abrindo a tela. Falha ao carregar não mostra nada: o card segue
 * levando à tela, onde o erro aparece.
 */
function AvisoDiarias() {
  const faixas = useQuery({ queryKey: qk.diarias.faixas, queryFn: ({ signal }) => listarFaixas(signal) });
  const valores = useQuery({ queryKey: qk.diarias.valores, queryFn: ({ signal }) => listarValores(signal) });
  if (!faixas.data || !valores.data) return null;
  const lacunas = lacunasDeValor(faixas.data, valores.data, hojeIso());
  const semValor = lacunas.filter((l) => l.tipo === "sem-valor").length;
  const acabam = lacunas.length - semValor;
  if (lacunas.length === 0) return null;
  const plural = (n: number) => (n > 1 ? `${n} faixas` : "1 faixa");
  return (
    <p
      className={`mt-2 w-fit rounded-full px-2 py-0.5 text-xs font-medium ${
        semValor > 0 ? "bg-error-bg text-error-text" : "bg-warning-bg text-warning-text"
      }`}
      data-testid="configuracao-aviso-diarias"
    >
      {semValor > 0
        ? `${plural(semValor)} sem valor vigente`
        : `${plural(acabam)} com valor que termina sem substituto`}
    </p>
  );
}

function HeaderSlot() {
  return (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">Configurações</h1>
    </PageHeader>
  );
}

export default function ConfiguracoesPage() {
  const { loading, isSuperAdmin } = useIsSuperAdmin();

  if (loading) {
    return (
      <>
        <HeaderSlot />
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner className="h-6 w-6 animate-spin text-text-muted" />
        </div>
      </>
    );
  }

  if (!isSuperAdmin) {
    return (
      <>
        <HeaderSlot />
        <RestrictedAccess />
      </>
    );
  }

  return (
    <>
      <HeaderSlot />

      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <Breadcrumb items={[{ label: "Início", href: "/dashboard" }, { label: "Configurações" }]} />

        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-text">Configurações</h2>
          <p className="mt-1 text-sm text-text-muted">Parâmetros dos módulos do sistema.</p>
        </div>

        {SECOES.map(({ modulo, itens }) => (
          <section key={modulo} className="flex flex-col gap-3" aria-label={modulo}>
            <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-text-muted">{modulo}</h3>
            <ul className="flex flex-col gap-3">
              {itens.map(({ href, titulo, descricao, Icon }) => (
                <li key={href}>
                  <Link
                    href={href}
                    className="group flex items-start gap-4 rounded-lg border border-border bg-surface p-5 transition hover:border-primary hover:bg-surface-muted/40 focus-visible:border-primary focus-visible:outline-none"
                    data-testid={`configuracao-card-${href.split("/").pop()}`}
                  >
                    <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-muted transition group-hover:bg-primary/10 group-hover:text-primary">
                      <Icon className="h-5 w-5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-text">{titulo}</p>
                      <p className="mt-1 text-sm text-text-muted">{descricao}</p>
                      {href === "/admin/configuracoes/sgd/diarias" && <AvisoDiarias />}
                    </div>
                    <ChevronRight className="h-5 w-5 shrink-0 text-text-muted transition group-hover:text-primary" />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
