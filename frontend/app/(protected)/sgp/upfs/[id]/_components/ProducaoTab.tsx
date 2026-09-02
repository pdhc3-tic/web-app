"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Pencil, Plus, Sprout, Trash2 } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { useToast } from "@/app/components/ui/Toast/Toast";
import {
  listProducoes,
  SISTEMA_CRIACAO_OPTIONS,
  TIPO_OUTRA_OPTIONS,
  type Producao,
  type TipoProducao,
} from "@/app/lib/producao";
import { ProducaoSlideOver, type SlideOverMode } from "./ProducaoSlideOver";
import { RemoverProducaoDialog } from "./RemoverProducaoDialog";

type Props = { upfId: string };
type SlideOverState = { open: false } | { open: true; mode: SlideOverMode; producao?: Producao };

export function ProducaoTab({ upfId }: Props) {
  const [producoes, setProducoes] = useState<Producao[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [slideOver, setSlideOver] = useState<SlideOverState>({ open: false });
  const [remover, setRemover] = useState<Producao | null>(null);
  const { showToast } = useToast();

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);
    listProducoes(upfId, controller.signal)
      .then((data) => setProducoes(data))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(e instanceof Error ? e.message : "Não foi possível carregar as atividades.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [upfId, reloadKey]);

  function handleSaved(saved: Producao) {
    setProducoes((prev) => {
      const idx = prev.findIndex((p) => p.id === saved.id);
      if (idx === -1) return [saved, ...prev];
      const next = [...prev];
      next[idx] = saved;
      return next;
    });
    showToast(slideOver.open && slideOver.mode === "edit" ? "Atividade atualizada." : "Atividade adicionada.");
    setSlideOver({ open: false });
  }

  function handleDeleted(id: number) {
    setProducoes((prev) => prev.filter((p) => p.id !== id));
    setRemover(null);
    showToast("Atividade removida.");
  }

  return (
    <div className="space-y-4">
      {!loading && !error && producoes.length > 0 && (
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-text-muted">
            {producoes.length}{" "}
            {producoes.length === 1 ? "atividade cadastrada" : "atividades cadastradas"}
          </p>
          <Button
            size="sm"
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() => setSlideOver({ open: true, mode: "create" })}
          >
            Adicionar atividade produtiva
          </Button>
        </div>
      )}

      {loading && <TabelaSkeleton />}

      {!loading && error && <ErroSection message={error} onRetry={() => setReloadKey((k) => k + 1)} />}

      {!loading && !error && producoes.length === 0 && (
        <EmptyState
          icon={<Sprout className="h-7 w-7" />}
          title="Nenhuma atividade produtiva cadastrada"
          description="Cadastre culturas agrícolas, criações pecuárias ou outras atividades."
          action={
            <Button
              leftIcon={<Plus className="h-4 w-4" />}
              onClick={() => setSlideOver({ open: true, mode: "create" })}
            >
              Adicionar atividade produtiva
            </Button>
          }
        />
      )}

      {!loading && !error && producoes.length > 0 && (
        <Tabela
          producoes={producoes}
          onEdit={(p) => setSlideOver({ open: true, mode: "edit", producao: p })}
          onRemove={(p) => setRemover(p)}
        />
      )}

      <ProducaoSlideOver
        open={slideOver.open}
        onClose={() => setSlideOver({ open: false })}
        mode={slideOver.open ? slideOver.mode : "create"}
        upfId={upfId}
        producao={slideOver.open ? slideOver.producao : undefined}
        onSaved={handleSaved}
      />

      <RemoverProducaoDialog
        open={remover !== null}
        onClose={() => setRemover(null)}
        upfId={upfId}
        producaoId={remover?.id ?? null}
        descricao={remover ? atividadeNome(remover) : ""}
        onDeleted={handleDeleted}
      />

    </div>
  );
}

function Tabela({
  producoes,
  onEdit,
  onRemove,
}: {
  producoes: Producao[];
  onEdit: (p: Producao) => void;
  onRemove: (p: Producao) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full min-w-180 border-collapse text-sm">
          <thead className="bg-surface-muted text-left text-2xs font-semibold uppercase tracking-wide text-text-muted">
            <tr>
              <th className="px-4 py-2.5">Tipo</th>
              <th className="px-4 py-2.5">Atividade</th>
              <th className="px-4 py-2.5">Quantitativo</th>
              <th className="px-4 py-2.5">Sistema/Categoria</th>
              <th className="px-4 py-2.5">Custo anual</th>
              <th className="px-4 py-2.5 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            {producoes.map((p) => (
              <tr key={p.id} className="border-t border-border align-middle transition hover:bg-surface-muted/40">
                <td className="px-4 py-3">
                  <TipoBadge tipo={p.tipo} />
                </td>
                <td className="px-4 py-3 font-medium text-text">{atividadeNome(p)}</td>
                <td className="px-4 py-3 text-text-muted">{quantitativo(p) || "—"}</td>
                <td className="px-4 py-3 text-text-muted">{sistemaOuCategoria(p) || "—"}</td>
                <td className="px-4 py-3 font-mono tabular-nums text-text-muted">{formatMoney(p.custo_anual) || "—"}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <AcaoIcone title="Editar" onClick={() => onEdit(p)} icon={<Pencil className="h-4 w-4" />} />
                    <AcaoIcone title="Remover" onClick={() => onRemove(p)} icon={<Trash2 className="h-4 w-4" />} danger />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TipoBadge({ tipo }: { tipo: TipoProducao }) {
  const map: Record<TipoProducao, { label: string; cls: string }> = {
    agricola: { label: "Agrícola", cls: "border-success-text bg-success-bg text-success-text" },
    pecuaria: { label: "Pecuária", cls: "border-warning-text bg-warning-bg text-warning-text" },
    outra: { label: "Outra", cls: "border-border bg-surface-muted text-text-muted" },
  };
  const { label, cls } = map[tipo];
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-2xs font-semibold ${cls}`}>
      {label}
    </span>
  );
}

function atividadeNome(p: Producao): string {
  if (p.tipo === "agricola") return p.cultura?.nome ?? "—";
  if (p.tipo === "pecuaria") return p.especie?.nome ?? "—";
  return p.descricao_outra?.trim() || "—";
}

function quantitativo(p: Producao): string {
  if (p.tipo === "agricola") {
    const partes: string[] = [];
    if (p.area_ha) partes.push(`${formatDecimal(p.area_ha)} ha`);
    if (p.producao_estimada) {
      partes.push(`${formatDecimal(p.producao_estimada)}${p.unidade_producao ? ` ${p.unidade_producao}` : ""}`);
    }
    return partes.join(" · ");
  }
  if (p.tipo === "pecuaria") {
    const partes: string[] = [];
    if (p.n_matrizes != null) partes.push(`${p.n_matrizes} matrizes`);
    if (p.n_reprodutores != null) partes.push(`${p.n_reprodutores} reprodutores`);
    if (p.n_jovens != null) partes.push(`${p.n_jovens} jovens`);
    return partes.join(" · ");
  }
  return p.quantidade_produzida ?? "";
}

function sistemaOuCategoria(p: Producao): string {
  if (p.tipo === "agricola") return p.cultura?.categoria ?? "";
  if (p.tipo === "pecuaria") {
    const sistema = SISTEMA_CRIACAO_OPTIONS.find((s) => s.value === p.sistema_criacao)?.label;
    const categoria = p.especie?.categoria;
    return [categoria, sistema].filter(Boolean).join(" · ");
  }
  return TIPO_OUTRA_OPTIONS.find((t) => t.value === p.tipo_outra)?.label ?? "";
}

function formatDecimal(v: string): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return v;
  return n.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}

function formatMoney(v: string | null): string {
  if (!v) return "";
  const n = Number(v);
  if (!Number.isFinite(n)) return "";
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function AcaoIcone({
  title,
  onClick,
  icon,
  danger,
}: {
  title: string;
  onClick: () => void;
  icon: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition hover:bg-surface-muted ${
        danger ? "hover:text-error-text" : "hover:text-text"
      }`}
    >
      {icon}
    </button>
  );
}

function TabelaSkeleton() {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="border-b border-border bg-surface-muted px-4 py-2.5">
        <div className="h-3 w-24 rounded bg-border" />
      </div>
      <ul className="divide-y divide-border">
        {Array.from({ length: 3 }).map((_, i) => (
          <li key={i} className="flex items-center gap-4 px-4 py-4">
            <div className="h-4 w-16 rounded bg-border/70" />
            <div className="h-4 w-40 rounded bg-border/50" />
            <div className="h-4 w-24 rounded bg-border/50" />
            <div className="ml-auto h-4 w-24 rounded bg-border/50" />
          </li>
        ))}
      </ul>
    </div>
  );
}

function ErroSection({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
        <AlertTriangle className="h-6 w-6" />
      </span>
      <p className="max-w-sm text-sm text-text-muted">{message}</p>
      <Button variant="secondary" onClick={onRetry}>Tentar novamente</Button>
    </div>
  );
}

