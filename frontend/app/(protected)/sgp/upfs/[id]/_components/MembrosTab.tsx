"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
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
import { CrudTab } from "@/app/components/sgp/CrudTab/CrudTab";
import { ConfirmDeleteDialog } from "@/app/components/ui/ConfirmDeleteDialog/ConfirmDeleteDialog";
import { qk } from "@/app/lib/queryKeys";
import {
  calcIdade,
  deleteMembro,
  exportarMembrosCsv,
  ExportMembrosTimeoutError,
  getResumoMembros,
  listMembros,
  type MembroDetail,
  type MembroListItem,
} from "@/app/lib/membros";
import { maskCpf } from "@/app/lib/format";
import { ComposicaoResumoCard } from "./ComposicaoResumoCard";
import {
  MembroSlideOver,
  type SensitivePermissions,
  type SlideOverMode,
} from "./MembroSlideOver";

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
  const queryClient = useQueryClient();
  const listaKey = qk.upf(upfId).membros;
  const resumoKey = qk.upf(upfId).membrosResumo;

  const {
    data: membros = [] as MembroListItem[],
    isPending: loading,
    error,
    refetch: refetchLista,
  } = useQuery({
    queryKey: listaKey,
    queryFn: ({ signal }) => listMembros(upfId, signal),
  });

  const {
    data: resumo = null,
    isPending: resumoLoading,
    error: resumoError,
    refetch: refetchResumo,
  } = useQuery({
    queryKey: resumoKey,
    queryFn: ({ signal }) => getResumoMembros(upfId, signal),
  });

  const errorMessage =
    error instanceof ApiError
      ? error.message
      : error
        ? "Não foi possível carregar."
        : null;
  const resumoErro = resumoError !== null;

  const reloadResumo = () => {
    void refetchResumo();
  };

  const [slideOver, setSlideOver] = useState<SlideOverState>({ open: false });
  const [remover, setRemover] = useState<MembroListItem | null>(null);
  const [exporting, setExporting] = useState(false);
  const { showToast } = useToast();

  /**
   * Baixa o CSV de membros (#191). As colunas vêm prontas do backend, que
   * omite as sensíveis conforme o perfil (BE-25) — nada aqui depende disso:
   * o arquivo desce como veio.
   */
  async function handleExport() {
    if (exporting) return;
    setExporting(true);
    try {
      const nome = await exportarMembrosCsv(upfId);
      showToast(`Download iniciado: ${nome}`);
    } catch (e) {
      const mensagem =
        e instanceof ExportMembrosTimeoutError
          ? "A geração do arquivo excedeu o tempo limite. Tente novamente."
          : e instanceof ApiError
            ? e.message
            : "Não foi possível gerar o arquivo. Tente novamente.";
      showToast(mensagem, "error");
    } finally {
      setExporting(false);
    }
  }


  const titularExists = useMemo(
    () => membros.some((m) => m.grau_parentesco === "titular"),
    [membros],
  );

  /**
   * Há Titular na UPF? `null` enquanto o resumo não respondeu — o alerta não
   * pode aparecer antes disso.
   *
   * `resumoLoading` vem primeiro na cadeia, e não só a ausência de `resumo`:
   * na revalidação disparada por salvar/remover, o resumo anterior continua em
   * memória (de propósito — os números não devem sumir da tela a cada
   * gravação), mas ele descreve o estado *antes* da alteração. Afirmar o
   * alerta a partir dele é afirmar por antecipação do mesmo jeito que derivá-lo
   * da listagem era: quem acabou de promover alguém a Titular veria o aviso
   * insistir até a resposta chegar. Enquanto a consulta está em voo — primeira
   * ou não — o valor é "ainda não sei".
   *
   * Fora do carregamento, o resumo (BE-23) é a fonte da verdade: ele conta no
   * banco, sem depender da página carregada. A listagem só entra como fallback
   * depois de uma falha efetiva da chamada, para o alerta não sumir junto com
   * ela.
   */
  const semTitular: boolean | null = resumoLoading
    ? null
    : resumo
      ? !resumo.tem_titular
      : resumoErro
        ? !titularExists
        : null;

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

    queryClient.setQueryData<MembroListItem[]>(listaKey, (prev = []) => {
      const idx = prev.findIndex((m) => m.id === saved.id);
      if (idx === -1) return [listItem, ...prev];
      const next = [...prev];
      next[idx] = listItem;
      return next;
    });

    // Resumo (BE-23) precisa refazer o count — não dá para simular otimista
    // com precisão (ele agrega faixas etárias e gênero, cálculos que o backend
    // faz). `invalidateQueries` marca stale e refaz a chamada.
    void queryClient.invalidateQueries({ queryKey: resumoKey });
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
    queryClient.setQueryData<MembroListItem[]>(listaKey, (prev = []) =>
      prev.filter((m) => m.id !== id),
    );
    void queryClient.invalidateQueries({ queryKey: resumoKey });
    setRemover(null);
    showToast("Membro removido.");
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4" data-testid="membros-tab">
      {/* Card-resumo — aparece também com a UPF vazia. Total zero e faixas
          zeradas são informação, e é justamente aí que o alerta de "sem
          Titular" mais importa; escondê-lo junto com a lista tirava da tela o
          único aviso de que a UPF está irregular. O alerta em si só entra
          depois que o resumo responde — ver `semTitular`. */}
      {!loading && !error && (
        <ComposicaoResumoCard
          resumo={resumo}
          loading={resumoLoading}
          semTitular={semTitular}
          onRetry={reloadResumo}
        />
      )}

      {/* A barra de ações continua atrelada à lista: exportar CSV de uma UPF
          sem membros não tem o que gerar, e o CTA de cadastro com zero membros
          é o do EmptyState logo abaixo ("Adicionar primeiro membro"). */}
      <CrudTab
        loading={loading}
        error={errorMessage}
        onRetry={() => {
          void refetchLista();
          void refetchResumo();
        }}
        skeleton={<CarregandoSection />}
      >
        {membros.length > 0 && (
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

        {membros.length === 0 && (
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

        {membros.length > 0 && (
          <Tabela
            membros={membros}
            onView={openView}
            onEdit={openEdit}
            onRemove={(m) => setRemover(m)}
          />
        )}
      </CrudTab>

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

      <ConfirmDeleteDialog
        open={remover !== null}
        onClose={() => setRemover(null)}
        title="Remover membro"
        itemName={remover?.nome_completo ?? ""}
        description="Esta ação será registrada no histórico mas não poderá ser desfeita."
        onConfirm={async () => {
          if (remover === null) return;
          await deleteMembro(upfId, remover.id);
          handleDeleteConfirmed(remover.id);
        }}
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

