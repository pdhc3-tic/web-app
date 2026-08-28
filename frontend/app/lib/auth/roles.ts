"use client";

import { useSession } from "next-auth/react";
import type { User } from "./types";

/** Slug do perfil com bypass total (espelha apps/core seed_core::ROLES). */
export const SUPER_ADMIN_SLUG = "super-admin";

/** Slug do perfil da Unidade de Gestão do Projeto (acesso global). */
export const UGP_SLUG = "ugp";

/** Slug do Articulador Estadual — acesso restrito aos seus estados. */
export const ARTICULADOR_ESTADUAL_SLUG = "articulador-estadual";

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
 * Espelha `ConflictLogViewSet.get_queryset`: Super Admin e UGP enxergam tudo, o
 * Articulador Estadual enxerga os territórios dos seus estados, e os demais
 * perfis recebem lista vazia. A issue cita apenas Articulador e Super Admin,
 * mas esconder a tela da UGP não a impediria de ler os mesmos dados pela API —
 * se o acesso tiver de ser menor, o limite nasce no backend.
 */
export function canReviewSyncConflicts(
  user: Pick<NonNullable<User>, "perfis"> | null | undefined,
): boolean {
  return (
    isSuperAdmin(user) ||
    hasRole(user, UGP_SLUG) ||
    hasRole(user, ARTICULADOR_ESTADUAL_SLUG)
  );
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
