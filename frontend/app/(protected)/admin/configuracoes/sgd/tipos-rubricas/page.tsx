"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
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
import { absoluteDateTime } from "@/app/lib/datetime";
import { qk } from "@/app/lib/queryKeys";
import {
  AVISO_NAO_RETROAGE,
  ERRO_DUPLICADO,
  atualizarMapeamento,
  conflitoDeAtivo,
  criarMapeamento,
  listMapeamentos,
  removerMapeamento,
  type MapeamentoPayload,
  type MapeamentoTipoRubrica,
} from "@/app/lib/tipoRubrica";
import { useRotuloChoice } from "@/app/providers/SgpChoicesProvider";
import { MapeamentoForm } from "./_components/MapeamentoForm";

const TH_BASE =
  "sticky top-0 z-10 bg-surface-muted px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-[0.08em] text-text-muted whitespace-nowrap";

function HeaderSlot() {
  return (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">Tipos e Rubricas</h1>
    </PageHeader>
  );
}

/**
 * Configurações → SGD → Tipos e Rubricas (#319): de qual rubrica sai o recurso
 * de cada tipo de solicitação. CRUD da BE-8, só Super Admin.
 */
export default function TiposRubricasPage() {
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
      <TiposRubricas />
    </>
  );
}

function TiposRubricas() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const tipoLabel = useRotuloChoice("solicitacao_tipo");
  const [incluirInativos, setIncluirInativos] = useState(false);
  const [form, setForm] = useState<{ editando: MapeamentoTipoRubrica | null } | null>(null);
  const [mudandoSituacao, setMudandoSituacao] = useState<MapeamentoTipoRubrica | null>(null);
  const [removendo, setRemovendo] = useState<MapeamentoTipoRubrica | null>(null);

  const lista = useQuery({
    queryKey: qk.configSgd.tipoRubricaLista(incluirInativos),
    queryFn: ({ signal }) => listMapeamentos({ incluirInativos }, signal),
  });
  const mapeamentos = lista.data ?? [];

  async function recarregar() {
    await queryClient.invalidateQueries({ queryKey: qk.configSgd.tipoRubrica });
  }

  async function salvar(payload: MapeamentoPayload) {
    const editando = form?.editando ?? null;
    if (editando) {
      await atualizarMapeamento(editando.id, { rubrica: payload.rubrica, ativo: payload.ativo });
    } else {
      await criarMapeamento(payload);
    }
    setForm(null);
    showToast(`Mapeamento ${editando ? "atualizado" : "criado"}. ${AVISO_NAO_RETROAGE}`);
    await recarregar();
  }

  /** Desativar libera o tipo; reativar passa pela mesma regra do duplicado. */
  async function alternarSituacao(m: MapeamentoTipoRubrica) {
    try {
      await atualizarMapeamento(m.id, { ativo: !m.ativo });
      showToast(`Mapeamento ${m.ativo ? "desativado" : "reativado"}. ${AVISO_NAO_RETROAGE}`);
      setMudandoSituacao(null);
      await recarregar();
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Não foi possível alterar o mapeamento.", "error");
    }
  }

  function pedirSituacao(m: MapeamentoTipoRubrica) {
    if (!m.ativo && conflitoDeAtivo(mapeamentos, m.tipo, m.id)) {
      showToast(`${ERRO_DUPLICADO} Desative o atual antes de reativar este.`, "error");
      return;
    }
    setMudandoSituacao(m);
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Breadcrumb
        items={[
          { label: "Início", href: "/dashboard" },
          { label: "Configurações", href: "/admin/configuracoes" },
          { label: "SGD" },
          { label: "Tipos e Rubricas" },
        ]}
      />

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-2xl font-semibold tracking-tight text-text">Tipos e Rubricas</h2>
          <p className="mt-1 max-w-2xl text-sm text-text-muted">
            De qual rubrica do orçamento sai o recurso de cada tipo de solicitação. Cada tipo tem
            um mapeamento ativo; a rubrica é gravada na solicitação quando ela é criada.
          </p>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setForm({ editando: null })} data-testid="mapeamento-novo">
          Novo mapeamento
        </Button>
      </div>

      <label className="flex items-center gap-2 text-sm text-text">
        <input
          type="checkbox"
          checked={incluirInativos}
          onChange={(e) => setIncluirInativos(e.target.checked)}
          className="h-4 w-4 accent-(--color-primary)"
          data-testid="mapeamentos-incluir-inativos"
        />
        Mostrar inativos
      </label>

      {lista.isPending ? (
        <div role="status" className="flex min-h-[20vh] items-center justify-center gap-2 text-sm text-text-muted">
          <Spinner className="h-5 w-5 animate-spin" />
          Carregando mapeamentos…
        </div>
      ) : lista.isError ? (
        <TabErroSection
          message={lista.error instanceof ApiError ? lista.error.message : "Não foi possível carregar os mapeamentos."}
          onRetry={() => void lista.refetch()}
        />
      ) : mapeamentos.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface">
          <EmptyState
            icon={<ListTree className="h-7 w-7" />}
            title="Nenhum mapeamento"
            description="Sem mapeamento ativo, o sistema recusa as solicitações do tipo."
          />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="w-full border-collapse text-sm" data-testid="mapeamentos-tabela">
            <thead>
              <tr>
                <th className={TH_BASE}>Tipo de solicitação</th>
                <th className={TH_BASE}>Rubrica</th>
                <th className={TH_BASE}>Situação</th>
                <th className={TH_BASE}>Alterado em</th>
                <th className={`${TH_BASE} text-right`}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {mapeamentos.map((m) => (
                <tr key={m.id} className="border-t border-border" data-testid={`mapeamento-${m.id}`}>
                  <td className="px-4 py-3 font-medium text-text">{tipoLabel(m.tipo)}</td>
                  <td className="px-4 py-3 text-text">{m.rubrica_nome}</td>
                  <td className="px-4 py-3">
                    <Badge status={m.ativo ? "ativo" : "inativo"} label={m.ativo ? "Ativo" : "Inativo"} />
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-text-muted">{absoluteDateTime(m.atualizado_em)}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="ghost" onClick={() => setForm({ editando: m })} data-testid={`mapeamento-editar-${m.id}`}>
                        Editar
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => pedirSituacao(m)} data-testid={`mapeamento-situacao-${m.id}`}>
                        {m.ativo ? "Desativar" : "Reativar"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setRemovendo(m)} data-testid={`mapeamento-remover-${m.id}`}>
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

      {form && (
        <MapeamentoForm
          editando={form.editando}
          mapeamentos={mapeamentos}
          onClose={() => setForm(null)}
          onSalvar={salvar}
        />
      )}

      {mudandoSituacao && (
        <ConfirmarSituacao
          mapeamento={mudandoSituacao}
          tipoLabel={tipoLabel(mudandoSituacao.tipo)}
          onClose={() => setMudandoSituacao(null)}
          onConfirm={() => alternarSituacao(mudandoSituacao)}
        />
      )}

      <ConfirmDeleteDialog
        open={removendo !== null}
        onClose={() => setRemovendo(null)}
        title="Remover mapeamento"
        itemName={removendo ? `${tipoLabel(removendo.tipo)} → ${removendo.rubrica_nome}` : ""}
        description={`O mapeamento sai do histórico. Para só deixar de usá-lo, prefira desativar. ${AVISO_NAO_RETROAGE}`}
        onConfirm={async () => {
          if (!removendo) return;
          await removerMapeamento(removendo.id);
          setRemovendo(null);
          showToast("Mapeamento removido.");
          await recarregar();
        }}
      />
    </div>
  );
}

function ConfirmarSituacao({
  mapeamento,
  tipoLabel,
  onClose,
  onConfirm,
}: {
  mapeamento: MapeamentoTipoRubrica;
  tipoLabel: string;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  const [enviando, setEnviando] = useState(false);
  const desativar = mapeamento.ativo;

  return (
    <SlideOver
      open
      onClose={enviando ? () => {} : onClose}
      title={desativar ? "Desativar mapeamento" : "Reativar mapeamento"}
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
          <strong>{tipoLabel}</strong> → <strong>{mapeamento.rubrica_nome}</strong>
        </p>
        <p className="text-text-muted">
          {desativar
            ? "Sem um mapeamento ativo, o sistema recusa novas solicitações deste tipo até você criar ou reativar outro."
            : "Este passa a ser o mapeamento ativo do tipo."}{" "}
          {AVISO_NAO_RETROAGE}
        </p>
      </div>
    </SlideOver>
  );
}
