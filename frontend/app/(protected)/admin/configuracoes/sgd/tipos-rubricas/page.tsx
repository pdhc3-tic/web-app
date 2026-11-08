"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ListTree, Plus } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { ConfirmDeleteDialog } from "@/app/components/ui/ConfirmDeleteDialog/ConfirmDeleteDialog";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { useIsSuperAdmin } from "@/app/lib/auth/roles";
import { useTiposSolicitacao } from "@/app/lib/hooks/useTiposSolicitacao";
import { qk } from "@/app/lib/queryKeys";
import {
  atualizarTipoSolicitacao,
  criarTipoSolicitacao,
  removerTipoSolicitacao,
  type TipoSolicitacaoCatalogo,
  type TipoSolicitacaoPayload,
} from "@/app/lib/tiposSolicitacao";
import { AVISO_NAO_RETROAGE, TipoSolicitacaoForm } from "./_components/TipoSolicitacaoForm";

const TH_BASE =
  "sticky top-0 z-10 bg-surface-muted px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-[0.08em] text-text-muted whitespace-nowrap";

const TITULO = "Tipos de solicitação";

function HeaderSlot() {
  return (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">{TITULO}</h1>
    </PageHeader>
  );
}

/**
 * Configurações → SGD → Tipos de solicitação (#365): o catálogo de tipos
 * (`/sgd/config/tipos-solicitacao/`, #357), com a rubrica de cada um e os
 * campos do formulário. Substitui a tela de mapeamento tipo → rubrica da #319.
 * Só Super Admin.
 */
export default function TiposSolicitacaoPage() {
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
      <CatalogoTipos />
    </>
  );
}

function CatalogoTipos() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [form, setForm] = useState<{ editando: TipoSolicitacaoCatalogo | null } | null>(null);
  const [mudandoSituacao, setMudandoSituacao] = useState<TipoSolicitacaoCatalogo | null>(null);
  const [removendo, setRemovendo] = useState<TipoSolicitacaoCatalogo | null>(null);

  const lista = useTiposSolicitacao();
  const tipos = lista.data ?? [];

  async function recarregar() {
    // O formulário de solicitação e o filtro de tipos do /choices/ leem o mesmo catálogo.
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: qk.configSgd.tiposSolicitacao }),
      queryClient.invalidateQueries({ queryKey: qk.choices }),
    ]);
  }

  async function salvar(payload: TipoSolicitacaoPayload) {
    const editando = form?.editando ?? null;
    if (editando) {
      const { slug: _slug, ...alteracoes } = payload;
      void _slug;
      await atualizarTipoSolicitacao(editando.id, alteracoes);
    } else {
      await criarTipoSolicitacao(payload);
    }
    setForm(null);
    showToast(`Tipo ${editando ? "atualizado" : "criado"}. ${AVISO_NAO_RETROAGE}`);
    await recarregar();
  }

  async function alternarSituacao(t: TipoSolicitacaoCatalogo) {
    try {
      await atualizarTipoSolicitacao(t.id, { ativo: !t.ativo });
      showToast(`Tipo ${t.ativo ? "desativado" : "reativado"}. ${AVISO_NAO_RETROAGE}`);
      setMudandoSituacao(null);
      await recarregar();
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Não foi possível alterar o tipo.", "error");
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Breadcrumb
        items={[
          { label: "Início", href: "/dashboard" },
          { label: "Configurações", href: "/admin/configuracoes" },
          { label: "SGD" },
          { label: TITULO },
        ]}
      />

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-2xl font-semibold tracking-tight text-text">{TITULO}</h2>
          <p className="mt-1 max-w-2xl text-sm text-text-muted">
            Os tipos que o solicitante escolhe ao montar a demanda, a rubrica do orçamento de onde sai o recurso de
            cada um e os campos do formulário. A rubrica é gravada na solicitação quando ela é criada.
          </p>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setForm({ editando: null })} data-testid="tipo-novo">
          Novo tipo
        </Button>
      </div>

      {lista.isPending ? (
        <div role="status" className="flex min-h-[20vh] items-center justify-center gap-2 text-sm text-text-muted">
          <Spinner className="h-5 w-5 animate-spin" />
          Carregando tipos…
        </div>
      ) : lista.isError ? (
        <TabErroSection
          message={lista.error instanceof ApiError ? lista.error.message : "Não foi possível carregar os tipos."}
          onRetry={() => void lista.refetch()}
        />
      ) : tipos.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface">
          <EmptyState
            icon={<ListTree className="h-7 w-7" />}
            title="Nenhum tipo de solicitação"
            description="Sem tipo ativo, o solicitante não consegue montar uma demanda."
          />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="w-full border-collapse text-sm" data-testid="tipos-tabela">
            <thead>
              <tr>
                <th className={`${TH_BASE} text-right`}>Ordem</th>
                <th className={TH_BASE}>Tipo</th>
                <th className={TH_BASE}>Identificador</th>
                <th className={TH_BASE}>Rubrica</th>
                <th className={TH_BASE}>Situação</th>
                <th className={`${TH_BASE} text-right`}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {tipos.map((t) => (
                <tr key={t.id} className="border-t border-border" data-testid={`tipo-${t.slug}`}>
                  <td className="px-4 py-3 text-right tabular-nums text-text-muted">{t.ordem}</td>
                  <td className="px-4 py-3 font-medium text-text">{t.nome}</td>
                  <td className="px-4 py-3">
                    <code className="text-xs text-text-muted">{t.slug}</code>
                  </td>
                  <td className="px-4 py-3 text-text">{t.rubrica_nome}</td>
                  <td className="px-4 py-3">
                    <Badge status={t.ativo ? "ativo" : "inativo"} label={t.ativo ? "Ativo" : "Inativo"} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="ghost" onClick={() => setForm({ editando: t })} data-testid={`tipo-editar-${t.slug}`}>
                        Editar
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setMudandoSituacao(t)} data-testid={`tipo-situacao-${t.slug}`}>
                        {t.ativo ? "Desativar" : "Reativar"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setRemovendo(t)} data-testid={`tipo-remover-${t.slug}`}>
                        Remover
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {form && <TipoSolicitacaoForm editando={form.editando} onClose={() => setForm(null)} onSalvar={salvar} />}

      {mudandoSituacao && (
        <ConfirmarSituacao
          tipo={mudandoSituacao}
          onClose={() => setMudandoSituacao(null)}
          onConfirm={() => alternarSituacao(mudandoSituacao)}
        />
      )}

      <ConfirmDeleteDialog
        open={removendo !== null}
        onClose={() => setRemovendo(null)}
        title="Remover tipo de solicitação"
        itemName={removendo?.nome ?? ""}
        description="Só um tipo sem solicitações pode ser removido. Para deixar de oferecê-lo, prefira desativar."
        onConfirm={async () => {
          if (!removendo) return;
          try {
            await removerTipoSolicitacao(removendo.id);
            showToast("Tipo removido.");
            await recarregar();
          } catch (e) {
            showToast(e instanceof ApiError ? e.message : "Não foi possível remover o tipo.", "error");
          } finally {
            setRemovendo(null);
          }
        }}
      />
    </div>
  );
}

function ConfirmarSituacao({
  tipo,
  onClose,
  onConfirm,
}: {
  tipo: TipoSolicitacaoCatalogo;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  const [enviando, setEnviando] = useState(false);
  const desativar = tipo.ativo;

  return (
    <SlideOver
      open
      onClose={enviando ? () => {} : onClose}
      title={desativar ? "Desativar tipo" : "Reativar tipo"}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={enviando}>
            Manter como está
          </Button>
          <Button
            variant={desativar ? "danger" : "primary"}
            loading={enviando}
            onClick={async () => {
              setEnviando(true);
              await onConfirm();
              setEnviando(false);
            }}
            data-testid="situacao-confirmar"
          >
            {desativar ? "Desativar" : "Reativar"}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3 px-4 py-4 text-sm text-text" data-testid="situacao-drawer">
        <p>
          <strong>{tipo.nome}</strong> → <strong>{tipo.rubrica_nome}</strong>
        </p>
        <p className="text-text-muted">
          {desativar
            ? "O tipo sai do formulário de solicitação até ser reativado. As solicitações que já o usam não mudam."
            : "O tipo volta ao formulário de solicitação."}{" "}
          {AVISO_NAO_RETROAGE}
        </p>
      </div>
    </SlideOver>
  );
}
