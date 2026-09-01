"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Download,
  Eye,
  Pencil,
  Plus,
  Star,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { Chip } from "@/app/components/ui/Chip/Chip";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { useToast } from "@/app/components/ui/Toast/Toast";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import {
  calcIdade,
  exportarMembrosCsv,
  ExportMembrosPendenteError,
  ExportMembrosTimeoutError,
  getResumoMembros,
  listMembros,
  type MembroDetail,
  type MembroListItem,
  type ResumoMembros,
} from "@/app/lib/membros";
import { maskCpf } from "@/app/lib/format";
import { ComposicaoResumoCard } from "./ComposicaoResumoCard";
import {
  MembroSlideOver,
  type SensitivePermissions,
  type SlideOverMode,
} from "./MembroSlideOver";
import { RemoverMembroDialog } from "./RemoverMembroDialog";

type Props = {
  upfId: string;
};

type SlideOverState =
  | { open: false }
  | { open: true; mode: SlideOverMode; membro?: MembroListItem };

/**
 * Idade em anos completos. Prefere o valor que o backend já calcula
 * (MembroListSerializer.get_idade) e recai no cálculo local quando a lista vem
 * sem ele — as duas pontas usam a mesma regra.
 */
function idadeLabel(membro: MembroListItem): string {
  const anos = membro.idade ?? calcIdade(membro.data_nascimento);
  if (anos === null || anos === undefined) return "—";
  return anos === 1 ? "1 ano" : `${anos} anos`;
}

// ─── Componente principal ────────────────────────────────────────────────────

export function MembrosTab({ upfId }: Props) {
  const [membros, setMembros] = useState<MembroListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [resumo, setResumo] = useState<ResumoMembros | null>(null);
  const [resumoLoading, setResumoLoading] = useState(true);
  const [resumoKey, setResumoKey] = useState(0);

  const [slideOver, setSlideOver] = useState<SlideOverState>({ open: false });
  const [remover, setRemover] = useState<MembroListItem | null>(null);
  const [exporting, setExporting] = useState(false);
  const { showToast } = useToast();

  /**
   * Baixa o CSV de membros (#191). Enquanto BE-24 não existir, o endpoint
   * responde 404 → `ExportMembrosPendenteError`, e o toast diz "aguardando
   * backend" em vez do genérico "não foi possível gerar". Quando BE-24
   * subir, esta função funciona sem mais mudança.
   */
  async function handleExport() {
    if (exporting) return;
    setExporting(true);
    try {
      const nome = await exportarMembrosCsv(upfId);
      showToast(`Download iniciado: ${nome}`);
    } catch (e) {
      const mensagem =
        e instanceof ExportMembrosPendenteError
          ? e.message
          : e instanceof ExportMembrosTimeoutError
            ? "A geração do arquivo excedeu o tempo limite. Tente novamente."
            : e instanceof ApiError
              ? e.message
              : "Não foi possível gerar o arquivo. Tente novamente.";
      showToast(mensagem, "error");
    } finally {
      setExporting(false);
    }
  }

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

  // ── Carrega o resumo agregado (BE-23) ──────────────────────────────────────
  // Chave própria: a listagem é atualizada de forma otimista após salvar ou
  // remover, mas os agregados só o backend sabe recalcular.
  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setResumoLoading(true);

    getResumoMembros(upfId, controller.signal)
      .then((data) => setResumo(data))
      .catch(() => {
        if (!controller.signal.aborted) setResumo(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setResumoLoading(false);
      });

    return () => controller.abort();
  }, [upfId, resumoKey]);

  const titularExists = useMemo(
    () => membros.some((m) => m.grau_parentesco === "titular"),
    [membros],
  );

  // O resumo é a fonte da verdade sobre o Titular; a listagem só cobre o caso
  // em que a chamada do resumo falhou, para o alerta não sumir junto com ela.
  const semTitular = resumo ? !resumo.tem_titular : !titularExists;

  /**
   * Permissão do usuário para os campos sensíveis (#192/BE-25) — usada para o
   * modo `create` do SlideOver (view/edit derivam do próprio detalhe carregado).
   * Como a listagem só expõe `cor_raca`, usamos a presença dessa chave como
   * sinal compartilhado — a matriz de permissão de BE-25 (#187) trata Saúde e
   * Cor/Raça como o mesmo grupo. Se BE-25 introduzir permissões independentes,
   * este bloco precisa passar a checar Saúde por outra via.
   * Lista vazia: default otimista (mostra) — o backend rejeita no save.
   */
  const sensitivePermissions = useMemo<SensitivePermissions>(() => {
    if (membros.length === 0) return { corRaca: true, saude: true };
    const hasCorRaca = "cor_raca_display" in membros[0];
    return { corRaca: hasCorRaca, saude: hasCorRaca };
  }, [membros]);

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
    // Preserva a "ausência" do backend: se `cor_raca_display` não veio na
    // resposta (sem permissão), o listItem também não deve ter — a listagem
    // segue coerente com o sinal usado em #192.
    const listItem: MembroListItem = {
      id: saved.id,
      nome_completo: saved.nome_completo,
      data_nascimento: saved.data_nascimento,
      idade: saved.idade,
      grau_parentesco: saved.grau_parentesco,
      grau_parentesco_display: saved.grau_parentesco_display,
      cpf: saved.cpf,
      genero: saved.genero,
      genero_display: saved.genero_display,
      criado_em: saved.criado_em,
      ...("cor_raca" in saved ? { cor_raca: saved.cor_raca } : {}),
      ...("cor_raca_display" in saved
        ? { cor_raca_display: saved.cor_raca_display }
        : {}),
    };

    setMembros((prev) => {
      const idx = prev.findIndex((m) => m.id === saved.id);
      if (idx === -1) return [listItem, ...prev];
      const next = [...prev];
      next[idx] = listItem;
      return next;
    });

    setResumoKey((k) => k + 1);
    showToast(
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
    setResumoKey((k) => k + 1);
    setRemover(null);
    showToast("Membro removido.");
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4" data-testid="membros-tab">
      {/* Card-resumo — aparece também com a UPF vazia. Total zero e faixas
          zeradas são informação, e é justamente aí que o alerta de "sem
          Titular" mais importa; escondê-lo junto com a lista tirava da tela o
          único aviso de que a UPF está irregular. O alerta não pisca à espera
          do resumo: sem membros `semTitular` já é true pelo fallback da
          listagem, então ele entra junto com o card e não muda depois. */}
      {!loading && !error && (
        <ComposicaoResumoCard
          resumo={resumo}
          loading={resumoLoading}
          semTitular={semTitular}
          onRetry={() => setResumoKey((k) => k + 1)}
        />
      )}

      {/* A barra de ações continua atrelada à lista: exportar CSV de uma UPF
          sem membros não tem o que gerar, e o CTA de cadastro com zero membros
          é o do EmptyState logo abaixo ("Adicionar primeiro membro"). */}
      {!loading && !error && membros.length > 0 && (
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button
            size="sm"
            variant="secondary"
            leftIcon={
              exporting ? (
                <Spinner className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )
            }
            disabled={exporting}
            onClick={handleExport}
            data-testid="membros-exportar-csv"
          >
            {exporting ? "Exportando…" : "Exportar CSV"}
          </Button>
          <Button
            size="sm"
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={openCreate}
          >
            Adicionar membro
          </Button>
        </div>
      )}

      {loading && <CarregandoSection />}

      {!loading && error && (
        <ErroSection
          message={error}
          onRetry={() => {
            setReloadKey((k) => k + 1);
            setResumoKey((k) => k + 1);
          }}
        />
      )}

      {!loading && !error && membros.length === 0 && (
        <EmptyState
          icon={<Users className="h-7 w-7" />}
          title="Nenhum membro cadastrado ainda."
          description="O primeiro membro cadastrado deve ser o Titular da UPF."
          action={
            <Button
              leftIcon={<UserPlus className="h-4 w-4" />}
              onClick={openCreate}
              data-testid="membros-adicionar-primeiro"
            >
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
        // Sem titular na UPF, o próximo cadastro é obrigatoriamente ele — o
        // formulário já abre com o parentesco preenchido.
        parentescoPadrao={titularExists ? undefined : "titular"}
        sensitivePermissions={sensitivePermissions}
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
        membroNome={remover?.nome_completo ?? ""}
        onDeleted={handleDeleteConfirmed}
      />
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
    const titular = membros.filter((m) => m.grau_parentesco === "titular");
    const outros = membros.filter((m) => m.grau_parentesco !== "titular");
    return [...titular, ...outros];
  }, [membros]);

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full min-w-160 border-collapse text-sm">
          <thead className="bg-surface-muted text-left text-2xs font-semibold uppercase tracking-wide text-text-muted">
            <tr>
              <th className="px-4 py-2.5">Nome</th>
              <th className="px-4 py-2.5">Parentesco</th>
              <th className="px-4 py-2.5">Idade</th>
              <th className="px-4 py-2.5">Gênero</th>
              <th className="px-4 py-2.5">CPF</th>
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

/**
 * Saúde e Cor/Raça ficam de fora da listagem resumida de propósito: são campos
 * sensíveis e só aparecem no detalhe/formulário, sujeitos à regra de FE-25.
 */
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
  const isTitular = membro.grau_parentesco === "titular";

  return (
    <tr
      data-testid={`membro-row-${membro.id}`}
      className="cursor-pointer border-t border-border align-middle transition hover:bg-surface-muted/40"
      onClick={() => onView(membro)}
    >
      <td className="px-4 py-3 font-medium text-text">{membro.nome_completo}</td>
      <td className="px-4 py-3">
        {isTitular ? (
          <span
            data-testid="membro-badge-titular"
            className="inline-flex items-center gap-1 rounded-full border border-primary bg-primary/10 px-2 py-0.5 text-2xs font-semibold text-primary"
          >
            <Star className="h-3 w-3 fill-current" aria-hidden />
            {membro.grau_parentesco_display}
          </span>
        ) : (
          <Chip>{membro.grau_parentesco_display}</Chip>
        )}
      </td>
      <td className="px-4 py-3 text-text-muted">{idadeLabel(membro)}</td>
      <td className="px-4 py-3 text-text-muted">{membro.genero_display || "—"}</td>
      <td className="px-4 py-3 font-mono text-2xs text-text-muted tabular-nums">
        {membro.cpf ? maskCpf(membro.cpf) || membro.cpf : "—"}
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
      // A linha inteira abre o detalhe; sem parar a propagação, "Editar" e
      // "Remover" disparariam também o onClick do <tr>.
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition hover:bg-surface-muted ${
        danger ? "hover:text-error-text" : "hover:text-text"
      }`}
    >
      {icon}
    </button>
  );
}

// ─── Carregamento ────────────────────────────────────────────────────────────

function CarregandoSection() {
  return (
    <div className="space-y-2" data-testid="membros-loading">
      <p className="text-sm text-text-muted" role="status" aria-live="polite">
        Carregando membros…
      </p>
      <TabelaSkeleton />
    </div>
  );
}

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
