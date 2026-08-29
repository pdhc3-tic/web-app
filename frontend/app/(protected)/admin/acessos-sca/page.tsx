"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { AlertTriangle, Search, SearchX, Smartphone } from "lucide-react";
import { PageHeader } from "@/app/components/layout/PageHeader";
import Spinner from "@/app/components/icons/Spinner";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Input } from "@/app/components/ui/Input/Input";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import { RestrictedAccess } from "@/app/components/ui/RestrictedAccess/RestrictedAccess";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { ApiError } from "@/app/lib/api";
import { useIsSuperAdmin } from "@/app/lib/auth/roles";
import {
  listUsers,
  type AcessoResponse,
  type UserListItem,
} from "@/app/lib/users";
import { AcessosTable } from "./_components/AcessosTable";
import { AcessoDialog, type AcessoModo } from "./_components/AcessoDialog";

const SEARCH_DEBOUNCE_MS = 300;
const DEFAULT_LIMIT = 25;
const PAGE_SIZES = [25, 50, 100];

type DialogState = {
  modo: AcessoModo;
  user: UserListItem;
} | null;

/**
 * Revogação de Acesso de Técnico (BE-15).
 *
 * Fica em /admin — e não em /sca — pelo mesmo critério da tela de conflitos:
 * /sca descreve o aplicativo de campo, esta é uma tela de administração.
 *
 * A listagem é `GET /api/v1/users/?com_dispositivo=true`: só técnicos com ao
 * menos um dispositivo SCA vinculado, que é o universo em que o wipe remoto faz
 * sentido. Revogar NÃO altera `ativo`, então o revogado continua aparecendo na
 * listagem default (que filtra `ativo=true`) — é o que permite reativá-lo.
 *
 * O gate é o `useIsSuperAdmin()` + <RestrictedAccess/>, mesmo padrão de
 * /admin/usuarios e /admin/integracoes. A issue pede "redirecionado", mas o
 * precedente das outras duas telas do admin é a 403 — divergência registrada no
 * PR. O backend também barra com 403 (UserViewSet.permission_classes), então o
 * `forbidden` cobre o caso de a matriz do backend mudar sem o front saber.
 */
export default function AcessosSCAPage() {
  const { loading: authLoading, isSuperAdmin } = useIsSuperAdmin();
  const { data: session } = useSession();
  const { showToast } = useToast();

  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);

  const [users, setUsers] = useState<UserListItem[]>([]);
  const [count, setCount] = useState(0);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  // `dialog` guarda o conteúdo e `dialogOpen` só a visibilidade: o SlideOver
  // permanece montado durante a animação de saída, então zerar o conteúdo no
  // fechamento faria o painel piscar com a copy do outro modo enquanto desliza.
  const [dialog, setDialog] = useState<DialogState>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  // ── Debounce da busca ──────────────────────────────────────────────────────
  useEffect(() => {
    const id = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [search]);

  // Trocar o critério de busca zera a paginação. Só dispara quando o termo
  // debounced muda, não a cada render — supressão intencional do lint.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOffset(0);
  }, [debouncedSearch]);

  // ── Carga da listagem ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!isSuperAdmin) return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDataLoading(true);
    setError(null);

    listUsers(
      {
        limit,
        offset,
        search: debouncedSearch || undefined,
        comDispositivo: true,
        ordering: "nome",
      },
      controller.signal,
    )
      .then((data) => {
        setUsers(data.results);
        setCount(data.count);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 403) {
          setForbidden(true);
          return;
        }
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar os técnicos. Tente novamente.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setDataLoading(false);
      });

    return () => controller.abort();
  }, [isSuperAdmin, limit, offset, debouncedSearch, reloadKey]);

  /**
   * Atualiza a linha na hora, sem refetch: o critério pede que o status mude
   * "imediatamente, sem esperar o próximo sync". A flag vem da resposta do
   * backend; a autoria é derivada da sessão, já que o payload da ação não
   * devolve o objeto `acesso_revogado_por` (ele só existe na listagem).
   */
  const aplicarResultado = useCallback(
    (id: number, res: AcessoResponse) => {
      setUsers((prev) =>
        prev.map((u) =>
          u.id === id
            ? {
                ...u,
                acesso_revogado: res.acesso_revogado,
                acesso_revogado_em: res.acesso_revogado
                  ? new Date().toISOString()
                  : null,
                acesso_revogado_por: res.acesso_revogado
                  ? {
                      id: Number(session?.user?.id ?? 0),
                      nome: session?.user?.nome_completo ?? "—",
                    }
                  : null,
              }
            : u,
        ),
      );
    },
    [session],
  );

  const handleConfirmado = useCallback(
    (id: number, res: AcessoResponse) => {
      aplicarResultado(id, res);
      setDialogOpen(false);
      // A `message` do backend já descreve a consequência em pt-BR (wipe no
      // próximo sync / necessidade de novo login) — evita uma segunda cópia da
      // copy aqui, que sairia de sincronia com a do servidor.
      showToast(
        res.message ||
          (res.acesso_revogado
            ? "Acesso revogado."
            : "Acesso reativado."),
        "success",
      );
    },
    [aplicarResultado, showToast],
  );

  const handleRevogar = useCallback((user: UserListItem) => {
    setDialog({ modo: "revogar", user });
    setDialogOpen(true);
  }, []);

  const handleReativar = useCallback((user: UserListItem) => {
    setDialog({ modo: "reativar", user });
    setDialogOpen(true);
  }, []);

  const hasActiveFilters = useMemo(
    () => debouncedSearch !== "",
    [debouncedSearch],
  );

  const header = (
    <PageHeader>
      <h1 className="truncate text-base font-semibold text-text">
        Acessos SCA
      </h1>
    </PageHeader>
  );

  if (authLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    );
  }

  if (!isSuperAdmin || forbidden) {
    return (
      <>
        {header}
        <RestrictedAccess />
      </>
    );
  }

  const showEmpty = !dataLoading && !error && users.length === 0;
  const isFirstLoad = dataLoading && users.length === 0;

  return (
    <div data-testid="acessos-sca-page">
      {header}

      <div className="flex flex-col gap-4">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "Acessos SCA" },
          ]}
        />

        <p className="text-sm text-text-muted">
          Técnicos com dispositivo vinculado ao app de campo. Revogar o acesso
          encerra as sessões na hora e faz o app apagar os dados locais do
          aparelho no próximo sync.
        </p>

        <div className="max-w-md">
          <Input
            label="Técnico"
            placeholder="Nome ou e-mail"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            startIcon={<Search className="h-4 w-4" />}
            data-testid="acessos-busca"
          />
        </div>

        {error ? (
          <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-6 w-6" />
            </span>
            <p className="max-w-sm text-sm text-text-muted">{error}</p>
            <Button
              variant="secondary"
              onClick={() => setReloadKey((k) => k + 1)}
            >
              Tentar novamente
            </Button>
          </div>
        ) : isFirstLoad ? (
          <div className="flex min-h-[40vh] items-center justify-center">
            <Spinner className="h-6 w-6 animate-spin text-text-muted" />
          </div>
        ) : showEmpty ? (
          <div className="rounded-lg border border-border bg-surface">
            <EmptyState
              icon={
                hasActiveFilters ? (
                  <SearchX className="h-7 w-7" />
                ) : (
                  <Smartphone className="h-7 w-7" />
                )
              }
              title={
                hasActiveFilters
                  ? "Nenhum técnico com esse termo"
                  : "Nenhum técnico com dispositivo vinculado"
              }
              description={
                hasActiveFilters
                  ? "Ajuste a busca e tente novamente."
                  : "Quando um técnico autenticar no app SCA, o dispositivo é registrado e ele aparece aqui."
              }
              action={
                hasActiveFilters ? (
                  <Button variant="secondary" onClick={() => setSearch("")}>
                    Limpar busca
                  </Button>
                ) : undefined
              }
            />
          </div>
        ) : (
          <>
            <AcessosTable
              users={users}
              loading={dataLoading}
              onRevogar={handleRevogar}
              onReativar={handleReativar}
            />
            <Pagination
              count={count}
              offset={offset}
              limit={limit}
              onOffsetChange={setOffset}
              onLimitChange={(l) => {
                setLimit(l);
                setOffset(0);
              }}
              pageSizes={PAGE_SIZES}
              itemNoun={{ one: "técnico", other: "técnicos" }}
            />
          </>
        )}
      </div>

      <AcessoDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        // Os fallbacks só valem antes da primeira abertura: depois disso
        // `dialog` retém o último conteúdo, inclusive enquanto o painel fecha.
        modo={dialog?.modo ?? "revogar"}
        tecnicoId={dialog?.user.id ?? null}
        tecnicoNome={dialog?.user.nome_completo ?? ""}
        onConfirmado={handleConfirmado}
      />
    </div>
  );
}
