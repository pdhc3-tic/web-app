"use client";

import { useSession } from "next-auth/react";
import type { User } from "./types";

/** Slug do perfil com bypass total (espelha apps/core seed_core::ROLES). */
export const SUPER_ADMIN_SLUG = "super-admin";

/** Slug do perfil da Unidade de Gestão do Projeto (acesso global). */
export const UGP_SLUG = "ugp";

/** Slug do Articulador Estadual — acesso restrito aos seus estados. */
export const ARTICULADOR_ESTADUAL_SLUG = "articulador-estadual";

/** Slug do ADT/ACR — técnico de campo, restrito ao próprio território. */
export const ADT_ACR_SLUG = "adt-acr";

/** Verifica se o usuário possui um perfil com o slug informado. */
export function hasRole(
  user: Pick<NonNullable<User>, "perfis"> | null | undefined,
  slug: string,
): boolean {
  if (!user?.perfis) return false;
  return user.perfis.some((p) => p.slug === slug);
}

/** Verifica se o usuário é Super Admin. */
export function isSuperAdmin(
  user: Pick<NonNullable<User>, "perfis"> | null | undefined,
): boolean {
  return hasRole(user, SUPER_ADMIN_SLUG);
}

/**
 * Escrita no Plano de Trabalho (Metas e Ações).
 *
 * Espelha o `IsSuperAdmin | IsUGP` aplicado em create/update/destroy pelos
 * viewsets de apps/sgp/views/workplan.py. Serve só para esconder afordâncias —
 * quem manda é o backend.
 */
export function canManageWorkPlan(
  user: Pick<NonNullable<User>, "perfis"> | null | undefined,
): boolean {
  return isSuperAdmin(user) || hasRole(user, UGP_SLUG);
}

/**
 * Revisão dos conflitos de sincronização do SCA.
 *
 * O aceite libera apenas Articulador Estadual e Super Admin — a UGP fica de
 * fora, e é isso que esta regra reflete (menu e gate das telas).
 *
 * O recorte real é do backend e já existe: desde a PR #213,
 * `ConflictLogViewSet.get_queryset` (backend/apps/sca/views.py) devolve
 * `qs.none()` para o perfil `ugp`, e `resolver` nega pelo
 * `has_object_permission`. Esta função é a afordância correspondente — esconde
 * menu e tela de quem receberia lista vazia e 403.
 */
export function canReviewSyncConflicts(
  user: Pick<NonNullable<User>, "perfis"> | null | undefined,
): boolean {
  return isSuperAdmin(user) || hasRole(user, ARTICULADOR_ESTADUAL_SLUG);
}

/**
 * Painel de dispositivos e log de sincronização do SCA.
 *
 * Espelha `IsSuperAdminOrUGPReadOnly`, aplicado por `SyncDeviceListView` e
 * `SyncEventViewSet` (backend/apps/sca/views.py). Serve para esconder os cards
 * e afordâncias de quem receberia 403 — o limite real é o do backend.
 */
export function canViewScaAdmin(
  user: Pick<NonNullable<User>, "perfis"> | null | undefined,
): boolean {
  return isSuperAdmin(user) || hasRole(user, UGP_SLUG);
}

/**
 * ADT/ACR — o perfil sem nenhum nível acima do próprio território.
 *
 * No orçamento (§5.3.3) isso é estrutural, não cosmético:
 * `services/budget.py::resolver_nivel_painel` fixa esse perfil no nível
 * territorial e responde 403 a `estado=`, mesmo quando o `territorio=` enviado
 * junto é o dele. Oferecer os controles de estado/território a quem só receberia
 * 403 seria uma afordância que não leva a lugar nenhum.
 */
export function isAdtAcr(
  user: Pick<NonNullable<User>, "perfis"> | null | undefined,
): boolean {
  return hasRole(user, ADT_ACR_SLUG);
}

export type SuperAdminState = {
  /** true enquanto a sessão ainda está carregando. */
  loading: boolean;
  /** true apenas quando a sessão carregou e o usuário é Super Admin. */
  isSuperAdmin: boolean;
};

/**
 * Hook de conveniência para gatekeeping de telas restritas ao Super Admin.
 * Substitui o AuthContext (#23) usando a sessão Auth.js como fonte de verdade.
 */
export function useIsSuperAdmin(): SuperAdminState {
  const { data: session, status } = useSession();
  const loading = status === "loading";
  return {
    loading,
    isSuperAdmin: !loading && isSuperAdmin(session?.user),
  };
}

export type SyncConflictsAccessState = {
  /** true enquanto a sessão ainda está carregando. */
  loading: boolean;
  /** true apenas quando a sessão carregou e o perfil pode revisar conflitos. */
  canReview: boolean;
};

/** Gate da tela de conflitos de sincronização (`/sca/conflitos`). */
export function useCanReviewSyncConflicts(): SyncConflictsAccessState {
  const { data: session, status } = useSession();
  const loading = status === "loading";
  return {
    loading,
    canReview: !loading && canReviewSyncConflicts(session?.user),
  };
}

export type OrcamentoScopeState = {
  /** true enquanto a sessão ainda está carregando. */
  loading: boolean;
  /**
   * true quando o usuário é ADT/ACR — a tela esconde os seletores de nível e o
   * detalhamento nacional/estadual, e anuncia que a visão é do território dele.
   */
  soTerritorio: boolean;
};

/**
 * Gate do Painel de Orçamento (`/sgp/orcamento`): a leitura é liberada a
 * qualquer autenticado, então o que o perfil decide é o ALCANCE da tela, não o
 * acesso a ela. Ver `isAdtAcr`.
 */
export function useOrcamentoScope(): OrcamentoScopeState {
  const { data: session, status } = useSession();
  const loading = status === "loading";
  return {
    loading,
    soTerritorio: !loading && isAdtAcr(session?.user),
  };
}

/**
 * Distribuição orçamentária (§5.3.2) — quem pode escrever, e em que nível.
 *
 * Espelha `BudgetAllocationViewSet._autorizar`, que é bem mais estreito do que
 * "quem tem acesso ao orçamento":
 *
 * - UGP/Super Admin criam em qualquer nível; na prática a tela os coloca no
 *   ESTADUAL, que é o passo de §5.3.2 que lhes cabe (o nacional é o teto do
 *   TED, não algo que se distribui aqui).
 * - Articulador Estadual **só** cria no nível TERRITORIAL — a primeira guarda
 *   de `_autorizar` recusa nacional/estadual para quem não é global — e apenas
 *   em território que intersecte os seus estados.
 * - ADT/ACR não distribui nada: cai no `RestrictedAccess`.
 */
export function canDistribuirOrcamento(
  user: Pick<NonNullable<User>, "perfis"> | null | undefined,
): boolean {
  return (
    isSuperAdmin(user) ||
    hasRole(user, UGP_SLUG) ||
    hasRole(user, ARTICULADOR_ESTADUAL_SLUG)
  );
}

/** Nível em que o perfil grava — o mesmo que `_autorizar` aceitaria dele. */
export type NivelDistribuicao = "estadual" | "territorial";

export type DistribuicaoScopeState = {
  /** true enquanto a sessão ainda está carregando. */
  loading: boolean;
  /** true quando o perfil pode gravar alguma alocação. */
  pode: boolean;
  /** Nível que a tela vai gravar, ou null quando não pode gravar nada. */
  nivel: NivelDistribuicao | null;
  /**
   * Siglas dos estados do Articulador, para filtrar os destinos oferecidos.
   * Vazio para UGP/Super Admin, que não têm recorte — ver `nivel` antes de
   * interpretar: lista vazia aqui não quer dizer "nenhum estado".
   */
  estados: string[];
};

/**
 * Gate da tela de distribuição (`/sgp/orcamento/distribuicao`).
 *
 * Os estados do Articulador saem dos territórios que a sessão já carrega
 * (`/auth/me` devolve `territorios[].estados`), que é a mesma origem de
 * `_estados_do_articulador` no backend. Sem chamada extra.
 */
export function useDistribuicaoScope(): DistribuicaoScopeState {
  const { data: session, status } = useSession();
  const loading = status === "loading";
  const user = session?.user;

  const global = !loading && (isSuperAdmin(user) || hasRole(user, UGP_SLUG));
  const articulador =
    !loading && !global && hasRole(user, ARTICULADOR_ESTADUAL_SLUG);

  const estados = articulador
    ? [
        ...new Set(
          (user?.territorios ?? []).flatMap((t) => t.estados ?? []),
        ),
      ].sort()
    : [];

  return {
    loading,
    pode: global || articulador,
    nivel: global ? "estadual" : articulador ? "territorial" : null,
    estados,
  };
}

export type WorkPlanAccessState = {
  /** true enquanto a sessão ainda está carregando. */
  loading: boolean;
  /** true apenas quando a sessão carregou e o usuário é UGP ou Super Admin. */
  canManage: boolean;
};

/**
 * Hook para as telas do Plano de Trabalho: a leitura é liberada a qualquer
 * autenticado, então o gate controla apenas as ações de escrita (criar,
 * editar, excluir) — os demais perfis veem a tela em modo somente leitura.
 */
export function useCanManageWorkPlan(): WorkPlanAccessState {
  const { data: session, status } = useSession();
  const loading = status === "loading";
  return {
    loading,
    canManage: !loading && canManageWorkPlan(session?.user),
  };
}
