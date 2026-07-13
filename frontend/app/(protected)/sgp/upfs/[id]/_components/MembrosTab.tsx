"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  Pencil,
  Plus,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { ApiError } from "@/app/lib/api";
import {
  listMembros,
  type MembroDetail,
  type MembroListItem,
} from "@/app/lib/membros";
import { maskCpf } from "@/app/lib/format";
import { MembroSlideOver, type SlideOverMode } from "./MembroSlideOver";
import { RemoverMembroDialog } from "./RemoverMembroDialog";

type Props = {
  upfId: string;
};

type SlideOverState =
  | { open: false }
  | { open: true; mode: SlideOverMode; membro?: MembroListItem };

type Toast = {
  id: number;
  variant: "success" | "error";
  message: string;
};

// ─── Componente principal ────────────────────────────────────────────────────

export function MembrosTab({ upfId }: Props) {
  const [membros, setMembros] = useState<MembroListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [slideOver, setSlideOver] = useState<SlideOverState>({ open: false });
  const [remover, setRemover] = useState<MembroListItem | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);

  // ── Carrega a lista ────────────────────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    listMembros(upfId, controller.signal)
      .then((data) => setMembros(data))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar os membros.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [upfId, reloadKey]);

  const titularExists = useMemo(
    () => membros.some((m) => m.parentesco === "titular"),
    [membros],
  );

  // ── Toasts ─────────────────────────────────────────────────────────────────
  const pushToast = useCallback((variant: Toast["variant"], message: string) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, variant, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  // ── Handlers ───────────────────────────────────────────────────────────────
  function openCreate() {
    setSlideOver({ open: true, mode: "create" });
  }
  function openView(m: MembroListItem) {
    setSlideOver({ open: true, mode: "view", membro: m });
  }
  function openEdit(m: MembroListItem) {
    setSlideOver({ open: true, mode: "edit", membro: m });
  }
  function closeSlideOver() {
    setSlideOver({ open: false });
  }

  // Atualização otimista: substitui/insere a linha antes de qualquer coisa.
  // Como a chamada de API que produz `saved` já foi bem-sucedida no filho,
  // aqui é seguro apenas commitar o novo estado + toast + fechar.
  function handleSaved(saved: MembroDetail) {
    const listItem: MembroListItem = {
      id: saved.id,
      nome: saved.nome,
      data_nasc: saved.data_nasc,
      idade: saved.idade,
      parentesco: saved.parentesco,
      parentesco_display: saved.parentesco_display,
      cpf: saved.cpf,
      genero: saved.genero,
      cor_raca: saved.cor_raca,
      criado_em: saved.criado_em,
    };

    setMembros((prev) => {
      const idx = prev.findIndex((m) => m.id === saved.id);
      if (idx === -1) return [listItem, ...prev];
      const next = [...prev];
      next[idx] = listItem;
      return next;
    });

    pushToast(
      "success",
      slideOver.open && slideOver.mode === "edit"
        ? "Membro atualizado."
        : "Membro adicionado.",
    );
    closeSlideOver();
  }

  // Callback do diálogo — DELETE já foi confirmado pelo backend nesse ponto.
  // Basta remover a linha da lista, fechar o diálogo e disparar o toast.
  function handleDeleteConfirmed(id: number) {
    setMembros((prev) => prev.filter((m) => m.id !== id));
    setRemover(null);
    pushToast("success", "Membro removido.");
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Cabeçalho da aba com contagem + botão de adicionar */}
      {(!loading && !error && membros.length > 0) && (
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-text-muted">
            {membros.length}{" "}
            {membros.length === 1 ? "membro cadastrado" : "membros cadastrados"}
          </p>
          <Button size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={openCreate}>
            Adicionar membro
          </Button>
        </div>
      )}

      {loading && <TabelaSkeleton />}

      {!loading && error && (
        <ErroSection message={error} onRetry={() => setReloadKey((k) => k + 1)} />
      )}

      {!loading && !error && membros.length === 0 && (
        <EmptyState
          icon={<Users className="h-7 w-7" />}
          title="Nenhum membro cadastrado ainda"
          description="Adicione o titular e os demais integrantes da família."
          action={
            <Button leftIcon={<UserPlus className="h-4 w-4" />} onClick={openCreate}>
              Adicionar primeiro membro
            </Button>
          }
        />
      )}

      {!loading && !error && membros.length > 0 && (
        <Tabela
          membros={membros}
          onView={openView}
          onEdit={openEdit}
          onRemove={(m) => setRemover(m)}
        />
      )}

      <MembroSlideOver
        open={slideOver.open}
        onClose={closeSlideOver}
        mode={slideOver.open ? slideOver.mode : "create"}
        upfId={upfId}
        membroListItem={slideOver.open ? slideOver.membro : undefined}
        titularExists={titularExists}
        onSaved={handleSaved}
        onEditFromView={
          slideOver.open && slideOver.mode === "view" && slideOver.membro
            ? () =>
                setSlideOver({
                  open: true,
                  mode: "edit",
                  membro: slideOver.membro,
                })
            : undefined
        }
      />

      <RemoverMembroDialog
        open={remover !== null}
        onClose={() => setRemover(null)}
        upfId={upfId}
        membroId={remover?.id ?? null}
        membroNome={remover?.nome ?? ""}
        onDeleted={handleDeleteConfirmed}
      />

      <ToastStack toasts={toasts} />
    </div>
  );
}

// ─── Tabela ──────────────────────────────────────────────────────────────────

type TabelaProps = {
  membros: MembroListItem[];
  onView: (m: MembroListItem) => void;
  onEdit: (m: MembroListItem) => void;
  onRemove: (m: MembroListItem) => void;
};

function Tabela({ membros, onView, onEdit, onRemove }: TabelaProps) {
  // Titular sempre no topo; demais na ordem em que já vieram do backend.
  const ordenados = useMemo(() => {
    const titular = membros.filter((m) => m.parentesco === "titular");
    const outros = membros.filter((m) => m.parentesco !== "titular");
    return [...titular, ...outros];
  }, [membros]);

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead className="bg-surface-muted text-left text-2xs font-semibold uppercase tracking-wide text-text-muted">
            <tr>
              <th className="px-4 py-2.5">Nome</th>
              <th className="px-4 py-2.5">Parentesco</th>
              <th className="px-4 py-2.5">Idade</th>
              <th className="px-4 py-2.5">Gênero</th>
              <th className="px-4 py-2.5">CPF</th>
              <th className="px-4 py-2.5">Saúde</th>
              <th className="px-4 py-2.5 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            {ordenados.map((m) => (
              <LinhaMembro
                key={m.id}
                membro={m}
                onView={onView}
                onEdit={onEdit}
                onRemove={onRemove}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LinhaMembro({
  membro,
  onView,
  onEdit,
  onRemove,
}: {
  membro: MembroListItem;
  onView: (m: MembroListItem) => void;
  onEdit: (m: MembroListItem) => void;
  onRemove: (m: MembroListItem) => void;
}) {
  const isTitular = membro.parentesco === "titular";
  // Placeholder de "saúde" enquanto a lista virá via detail — a listagem hoje
  // não traz o array de saúde; representamos como "—" e ao abrir a linha via
  // "Ver" o SlideOver mostra o conjunto real.
  return (
    <tr className="border-t border-border align-middle transition hover:bg-surface-muted/40">
      <td className="px-4 py-3 font-medium text-text">{membro.nome}</td>
      <td className="px-4 py-3">
        {isTitular ? (
          <span className="inline-flex items-center rounded-full border border-primary bg-primary/10 px-2 py-0.5 text-2xs font-semibold text-primary">
            {membro.parentesco_display}
          </span>
        ) : (
          <Chip>{membro.parentesco_display}</Chip>
        )}
      </td>
      <td className="px-4 py-3 text-text-muted">
        {membro.idade !== null && membro.idade !== undefined
          ? `${membro.idade} anos`
          : "—"}
      </td>
      <td className="px-4 py-3 text-text-muted">{membro.genero || "—"}</td>
      <td className="px-4 py-3 font-mono text-2xs text-text-muted tabular-nums">
        {membro.cpf ? maskCpf(membro.cpf) || membro.cpf : "—"}
      </td>
      <td className="px-4 py-3">
        <SaudePreview />
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-1">
          <AcaoIcone
            title="Ver"
            onClick={() => onView(membro)}
            icon={<Eye className="h-4 w-4" />}
          />
          <AcaoIcone
            title="Editar"
            onClick={() => onEdit(membro)}
            icon={<Pencil className="h-4 w-4" />}
          />
          <AcaoIcone
            title="Remover"
            onClick={() => onRemove(membro)}
            icon={<Trash2 className="h-4 w-4" />}
            danger
          />
        </div>
      </td>
    </tr>
  );
}

// Placeholder discreto — a listagem paginada não carrega o campo `saude`.
// Ficou como "—" na tabela e o SlideOver mostra o conjunto completo.
// Mantido como componente separado para eventual evolução futura (ex.: prefetch).
function SaudePreview() {
  return <span className="text-text-muted">—</span>;
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

// ─── Skeleton ────────────────────────────────────────────────────────────────

function TabelaSkeleton() {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="border-b border-border bg-surface-muted px-4 py-2.5">
        <div className="h-3 w-24 rounded bg-border" />
      </div>
      <ul className="divide-y divide-border">
        {Array.from({ length: 4 }).map((_, i) => (
          <li key={i} className="flex items-center gap-4 px-4 py-4">
            <div className="h-4 w-40 rounded bg-border/70" />
            <div className="h-4 w-24 rounded bg-border/50" />
            <div className="h-4 w-16 rounded bg-border/50" />
            <div className="ml-auto h-4 w-24 rounded bg-border/50" />
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Erro de carregamento ────────────────────────────────────────────────────

function ErroSection({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
        <AlertTriangle className="h-6 w-6" />
      </span>
      <p className="max-w-sm text-sm text-text-muted">{message}</p>
      <Button variant="secondary" onClick={onRetry}>
        Tentar novamente
      </Button>
    </div>
  );
}

// ─── Toasts ──────────────────────────────────────────────────────────────────

function ToastStack({ toasts }: { toasts: Toast[] }) {
  if (toasts.length === 0) return null;
  return (
    <div
      className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2"
      role="status"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto flex items-center gap-2 rounded-md border px-3 py-2 text-sm shadow-md ${
            t.variant === "success"
              ? "border-success-text bg-success-bg text-success-text"
              : "border-error-text bg-error-bg text-error-text"
          }`}
        >
          {t.variant === "success" ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <AlertTriangle className="h-4 w-4" />
          )}
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  );
}
