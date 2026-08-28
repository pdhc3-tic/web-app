"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { absoluteDateTime, relativeTime } from "@/app/lib/datetime";
import {
  ENTIDADE_LABEL,
  formatarValor,
  rotuloCampo,
  type Conflito,
} from "@/app/lib/conflitos";
import { SensivelBadge, StatusConflitoBadge } from "./ConflitoBadges";

/**
 * Lista de conflitos.
 *
 * Tabela em telas largas e cartões no celular — mesmo padrão das listagens do
 * SGP. A linha inteira é um link para o detalhe: resolver exige contexto que não
 * cabe aqui, então a lista não oferece nenhuma ação de resolução direta.
 */
export function ConflitosTable({ conflitos }: { conflitos: Conflito[] }) {
  return (
    <div
      data-testid="conflitos-table"
      className="overflow-hidden rounded-lg border border-border bg-surface"
    >
      {/* Desktop */}
      <table className="hidden w-full border-collapse md:table">
        <thead>
          <tr className="border-b border-border text-left">
            <Th>Entidade e campo</Th>
            <Th>No aparelho</Th>
            <Th>No servidor</Th>
            <Th>Detectado</Th>
            <Th>Status</Th>
            <th className="w-10" />
          </tr>
        </thead>
        <tbody>
          {conflitos.map((c) => (
            <tr
              key={c.id}
              data-testid={`conflito-row-${c.id}`}
              data-sensivel={c.campo_sensivel ? "true" : "false"}
              className="border-b border-border last:border-b-0 transition-colors hover:bg-surface-muted"
            >
              <Td>
                <Link
                  href={`/sca/conflitos/${c.id}`}
                  className="flex flex-col gap-1 no-underline"
                  aria-label={`Abrir conflito de ${rotuloCampo(c.campo)}`}
                >
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium text-text">
                      {rotuloCampo(c.campo)}
                    </span>
                    {c.campo_sensivel && <SensivelBadge compacto />}
                  </span>
                  <span className="text-xs text-text-muted">
                    {ENTIDADE_LABEL[c.entidade] ?? c.entidade}
                    {c.territorio ? ` · ${c.territorio.nome}` : ""}
                  </span>
                </Link>
              </Td>
              <Td>
                <Valor valor={formatarValor(c.valor_local)} />
              </Td>
              <Td>
                <Valor valor={formatarValor(c.valor_servidor)} />
              </Td>
              <Td>
                <span
                  className="whitespace-nowrap text-xs text-text-muted"
                  title={absoluteDateTime(c.criado_em)}
                >
                  {relativeTime(c.criado_em)}
                </span>
              </Td>
              <Td>
                <StatusConflitoBadge status={c.status} />
              </Td>
              <Td>
                <Link
                  href={`/sca/conflitos/${c.id}`}
                  aria-label={`Abrir conflito ${c.id}`}
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-surface hover:text-text"
                >
                  <ChevronRight className="h-4 w-4" aria-hidden />
                </Link>
              </Td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile */}
      <ul className="flex flex-col md:hidden">
        {conflitos.map((c) => (
          <li
            key={c.id}
            data-testid={`conflito-card-${c.id}`}
            data-sensivel={c.campo_sensivel ? "true" : "false"}
            className="border-b border-border last:border-b-0"
          >
            <Link
              href={`/sca/conflitos/${c.id}`}
              className="flex flex-col gap-2 p-4 no-underline transition-colors hover:bg-surface-muted"
            >
              <span className="flex flex-wrap items-center gap-1.5">
                <span className="font-medium text-text">{rotuloCampo(c.campo)}</span>
                {c.campo_sensivel && <SensivelBadge compacto />}
              </span>
              <span className="text-xs text-text-muted">
                {ENTIDADE_LABEL[c.entidade] ?? c.entidade}
                {c.territorio ? ` · ${c.territorio.nome}` : ""}
              </span>
              <span className="flex flex-col gap-0.5 text-sm">
                <span className="text-text-muted">
                  Aparelho:{" "}
                  <span className="text-text">{formatarValor(c.valor_local)}</span>
                </span>
                <span className="text-text-muted">
                  Servidor:{" "}
                  <span className="text-text">{formatarValor(c.valor_servidor)}</span>
                </span>
              </span>
              <span className="flex items-center justify-between gap-2">
                <StatusConflitoBadge status={c.status} />
                <span
                  className="text-xs text-text-muted"
                  title={absoluteDateTime(c.criado_em)}
                >
                  {relativeTime(c.criado_em)}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Th({ children }: { children?: React.ReactNode }) {
  return (
    <th className="px-4 py-2.5 text-2xs font-medium uppercase tracking-[0.08em] text-text-muted">
      {children}
    </th>
  );
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-3 align-middle">{children}</td>;
}

/** Valores longos (nome completo, coordenada) não podem esticar a tabela. */
function Valor({ valor }: { valor: string }) {
  return (
    <span
      title={valor}
      className="block max-w-[16rem] truncate text-sm text-text"
    >
      {valor}
    </span>
  );
}
