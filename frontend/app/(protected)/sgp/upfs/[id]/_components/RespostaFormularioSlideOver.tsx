"use client";

import { useEffect, useState } from "react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import { absoluteDateTime, formatDate } from "@/app/lib/datetime";
import {
  getFormResponse,
  type FormResponseDetail,
  type FormResponseListItem,
  type RespostasJson,
  type RespostasJsonValor,
} from "@/app/lib/formularios";

type Props = {
  open: boolean;
  onClose: () => void;
  upfId: string | number;
  /**
   * Item da listagem — usado para pré-carregar cabeçalho (nome/versão/data)
   * enquanto o detalhe chega. `null` fecha o painel.
   */
  resposta: FormResponseListItem | null;
};

/**
 * Modal (SlideOver) de visualização completa de uma resposta de formulário.
 *
 * Renderiza `respostas_json` recursivamente com fallback genérico chave/valor
 * para qualquer valor cujo tipo o front não reconheça — o schema evolui no
 * SGF sem controle direto do SGP (critério #179).
 *
 * "Sem perder filtros aplicados" do critério é resolvido no nível da página:
 * os filtros vivem em query params da URL, e abrir/fechar o SlideOver não os
 * altera. Nada de estado adicional aqui.
 */
export function RespostaFormularioSlideOver({
  open,
  onClose,
  upfId,
  resposta,
}: Props) {
  const [detalhe, setDetalhe] = useState<FormResponseDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !resposta) return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDetalhe(null);
    setError(null);
    setLoading(true);

    getFormResponse(upfId, resposta.id, controller.signal)
      .then(setDetalhe)
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar a resposta.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [open, upfId, resposta]);

  const title = resposta?.formulario_nome ?? "Resposta de formulário";
  const cabecalho = detalhe ?? resposta;

  const footer = (
    <div className="flex justify-end">
      <Button variant="secondary" onClick={onClose}>
        Fechar
      </Button>
    </div>
  );

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={title}
      footer={footer}
      width="wide"
    >
      <div
        className="flex flex-col gap-6 px-4 py-4"
        data-testid="resposta-formulario-slideover"
      >
        <Cabecalho cabecalho={cabecalho} />

        {loading && !detalhe ? (
          <div className="flex min-h-[30vh] items-center justify-center">
            <Spinner className="h-6 w-6 animate-spin text-text-muted" />
          </div>
        ) : error ? (
          <p className="text-sm text-error-text">{error}</p>
        ) : detalhe ? (
          <RespostasBlock respostas={detalhe.respostas_json} />
        ) : null}
      </div>
    </SlideOver>
  );
}

function Cabecalho({
  cabecalho,
}: {
  cabecalho: FormResponseListItem | FormResponseDetail | null;
}) {
  if (!cabecalho) return null;
  const respondente = cabecalho.respondente?.trim() || "Anônimo";
  return (
    <section>
      <DefinitionList
        items={[
          { label: "Formulário", value: cabecalho.formulario_nome },
          { label: "Versão", value: cabecalho.formulario_versao },
          {
            label: "Data",
            value: (
              <span title={absoluteDateTime(cabecalho.data_preenchimento)}>
                {formatDate(cabecalho.data_preenchimento)}
              </span>
            ),
          },
          { label: "Respondente", value: respondente },
          {
            label: "Status",
            value: <StatusChip status={cabecalho.status} />,
          },
        ]}
      />
    </section>
  );
}

/** Chip de status compartilhado com a listagem (#178). */
export function StatusChip({
  status,
}: {
  status: "rascunho" | "submetido";
}) {
  const map = {
    submetido: {
      wrapper: "border-success-text/40 bg-success-bg text-success-text",
      label: "Submetido",
    },
    rascunho: {
      wrapper: "border-warning-text/40 bg-warning-bg text-warning-text",
      label: "Rascunho",
    },
  } as const;
  const s = map[status];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-2xs font-medium ${s.wrapper}`}
    >
      {s.label}
    </span>
  );
}

// ─── Renderização recursiva das respostas ────────────────────────────────────

function RespostasBlock({ respostas }: { respostas: RespostasJson }) {
  const entradas = Object.entries(respostas ?? {});
  if (entradas.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        Este formulário foi submetido sem respostas registradas.
      </p>
    );
  }
  return (
    <section>
      <h3 className="mb-3 text-2xs font-semibold uppercase tracking-wide text-text-muted">
        Respostas
      </h3>
      <div className="flex flex-col gap-3">
        {entradas.map(([chave, valor]) => (
          <Campo key={chave} chave={chave} valor={valor} nivel={0} />
        ))}
      </div>
    </section>
  );
}

/**
 * Renderiza um par chave/valor. Estratégia por tipo:
 * - object → sub-seção recursiva com título em maiúsculas.
 * - array → lista de <Chip> (primitivos) ou blocos aninhados (objetos).
 * - primitivo → linha "Chave: valor" formatada.
 * - null/undefined → "—".
 *
 * Um campo com tipo desconhecido (ex.: função, symbol — impossíveis vindo
 * de JSON, mas por defesa) cai no fallback `String(valor)` — nada quebra.
 */
function Campo({
  chave,
  valor,
  nivel,
}: {
  chave: string;
  valor: RespostasJsonValor;
  nivel: number;
}) {
  const rotulo = humanize(chave);

  if (valor === null || valor === undefined) {
    return <LinhaPrimitiva rotulo={rotulo} valor="—" />;
  }

  if (Array.isArray(valor)) {
    if (valor.length === 0) {
      return <LinhaPrimitiva rotulo={rotulo} valor="—" />;
    }
    const todosPrimitivos = valor.every(
      (item) => item === null || primitivo(item),
    );
    if (todosPrimitivos) {
      return (
        <div className="flex flex-col gap-1">
          <span className="text-xs text-text-muted">{rotulo}</span>
          <div className="flex flex-wrap gap-1.5">
            {valor.map((item, idx) => (
              <Chip key={idx}>{stringify(item)}</Chip>
            ))}
          </div>
        </div>
      );
    }
    return (
      <Bloco rotulo={rotulo} nivel={nivel}>
        <ol className="flex flex-col gap-2 pl-4">
          {valor.map((item, idx) => (
            <li key={idx} className="list-decimal">
              <Campo chave={`Item ${idx + 1}`} valor={item} nivel={nivel + 1} />
            </li>
          ))}
        </ol>
      </Bloco>
    );
  }

  if (typeof valor === "object") {
    const entradas = Object.entries(valor);
    if (entradas.length === 0) {
      return <LinhaPrimitiva rotulo={rotulo} valor="—" />;
    }
    return (
      <Bloco rotulo={rotulo} nivel={nivel}>
        <div className="flex flex-col gap-2">
          {entradas.map(([k, v]) => (
            <Campo key={k} chave={k} valor={v} nivel={nivel + 1} />
          ))}
        </div>
      </Bloco>
    );
  }

  return <LinhaPrimitiva rotulo={rotulo} valor={stringify(valor)} />;
}

function LinhaPrimitiva({
  rotulo,
  valor,
}: {
  rotulo: string;
  valor: string;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_2fr] items-baseline gap-3 text-sm">
      <span className="text-text-muted">{rotulo}</span>
      <span className="min-w-0 text-text">{valor}</span>
    </div>
  );
}

function Bloco({
  rotulo,
  nivel,
  children,
}: {
  rotulo: string;
  nivel: number;
  children: React.ReactNode;
}) {
  return (
    <div
      className={
        nivel === 0
          ? "rounded-md border border-border bg-surface-muted/40 px-3 py-2"
          : "border-l border-border pl-3"
      }
    >
      <p className="mb-2 text-2xs font-semibold uppercase tracking-wide text-text-muted">
        {rotulo}
      </p>
      {children}
    </div>
  );
}

function primitivo(v: unknown): boolean {
  const t = typeof v;
  return t === "string" || t === "number" || t === "boolean";
}

/** "renda_familiar" → "Renda familiar". Chaves já humanizadas ficam intactas. */
function humanize(chave: string): string {
  if (/\s/.test(chave)) return chave;
  const semSep = chave.replace(/[_-]+/g, " ").trim();
  return semSep.charAt(0).toUpperCase() + semSep.slice(1);
}

function stringify(v: RespostasJsonValor): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "Sim" : "Não";
  return String(v);
}
