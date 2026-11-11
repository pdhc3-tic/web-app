import { apiClient } from "@/app/lib/api";
import type { Perfil, Territorio } from "@/app/lib/auth/types";
import type { SelectOption } from "@/app/components/ui/Select/Select";

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** Autor de uma revogação — `acesso_revogado_por` do UserListSerializer. */
export type RevogadoPor = {
  id: number;
  nome: string;
};

/** Espelha apps/core/serializers.py::UserListSerializer. */
export type UserListItem = {
  id: number;
  nome_completo: string;
  email: string;
  perfis: Perfil[];
  territorios: Territorio[];
  ativo: boolean;
  ultimo_login: string | null;
  /**
   * Wipe remoto pendente: o app SCA apaga os dados locais no próximo sync e
   * exige novo login. Independe de `ativo` — um usuário revogado continua
   * ativo, então ele não some da listagem default (que filtra `ativo=true`).
   */
  acesso_revogado: boolean;
  acesso_revogado_em: string | null;
  acesso_revogado_por: RevogadoPor | null;
  /**
   * Só vêm preenchidos com `?com_dispositivo=true` — o backend anota os
   * agregados apenas nesse caso, para não pagar o N+1 nas demais listagens
   * (apps/core/views/users.py::UserViewSet.get_queryset).
   */
  qtd_dispositivos: number | null;
  ultimo_sync_dispositivos: string | null;
};

/** Resposta paginada padrão do DRF (LimitOffsetPagination). */
export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

/** Filtro de status mapeado para o parâmetro `ativo` do backend. */
export type StatusFilter = "ativos" | "inativos" | "todos";

export type ListUsersParams = {
  limit: number;
  offset: number;
  search?: string;
  perfil?: string;
  territorio?: string;
  status?: StatusFilter;
  /** Datas no formato YYYY-MM-DD (input nativo). */
  ultimoAcessoDe?: string;
  ultimoAcessoAte?: string;
  ordering?: string;
  /**
   * Restringe aos usuários com ao menos um dispositivo SCA vinculado e liga os
   * agregados `qtd_dispositivos` / `ultimo_sync_dispositivos`.
   */
  comDispositivo?: boolean;
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function buildUsersQuery(params: ListUsersParams): string {
  const qs = new URLSearchParams();
  qs.set("limit", String(params.limit));
  qs.set("offset", String(params.offset));

  if (params.search?.trim()) qs.set("search", params.search.trim());
  if (params.perfil) qs.set("perfil", params.perfil);
  if (params.territorio) qs.set("territorio", params.territorio);
  if (params.ordering) qs.set("ordering", params.ordering);
  if (params.comDispositivo) qs.set("com_dispositivo", "true");

  // Status → parâmetro `ativo`.
  // O backend só lista inativos quando `ativo` está presente na query
  // (caso contrário filtra ativo=True por padrão). Passar string vazia
  // mantém o parâmetro presente sem aplicar filtro → retorna todos.
  if (params.status === "ativos") qs.set("ativo", "true");
  else if (params.status === "inativos") qs.set("ativo", "false");
  else if (params.status === "todos") qs.set("ativo", "");

  // Range de último acesso: o "YYYY-MM-DD" do input vai cru. Desde a #212 o
  // backend recorta o dia no TIME_ZONE do servidor — converter para ISO em UTC
  // aqui era justamente o que deslocava a janela em horas.
  if (params.ultimoAcessoDe) qs.set("ultimo_acesso_de", params.ultimoAcessoDe);
  if (params.ultimoAcessoAte) {
    qs.set("ultimo_acesso_ate", params.ultimoAcessoAte);
  }

  return qs.toString();
}

// ─── API ────────────────────────────────────────────────────────────────────

/** GET /api/v1/users/ — listagem paginada (restrito a Super Admin no BE). */
export async function listUsers(
  params: ListUsersParams,
  signal?: AbortSignal,
): Promise<Paginated<UserListItem>> {
  const res = await apiClient(`/api/v1/users/?${buildUsersQuery(params)}`, {
    signal,
  });
  return res.json();
}

// ─── Acesso ao app SCA (revogar / reativar) ─────────────────────────────────

/**
 * Corpo devolvido por `revogar-acesso/` e `reativar-acesso/`.
 *
 * `message` já vem em pt-BR e descreve a consequência (wipe no próximo sync /
 * necessidade de novo login) — a tela usa esse texto direto no toast em vez de
 * manter uma segunda cópia da copy do lado do cliente.
 */
export type AcessoResponse = {
  message: string;
  acesso_revogado: boolean;
  /** Refresh tokens colocados na blacklist — todas as sessões do usuário. */
  sessoes_invalidadas: number;
};

/**
 * PATCH /api/v1/users/{id}/revogar-acesso/ — marca `acesso_revogado` e derruba
 * as sessões ativas. O apagamento dos dados locais acontece no próximo sync do
 * dispositivo; o efeito no servidor é imediato.
 */
export async function revogarAcesso(
  id: number,
  signal?: AbortSignal,
): Promise<AcessoResponse> {
  const res = await apiClient(`/api/v1/users/${id}/revogar-acesso/`, {
    method: "PATCH",
    signal,
  });
  return res.json();
}

/**
 * PATCH /api/v1/users/{id}/reativar-acesso/ — limpa a revogação. O backend
 * invalida as sessões de novo, então o técnico precisa de um login completo.
 */
export async function reativarAcesso(
  id: number,
  signal?: AbortSignal,
): Promise<AcessoResponse> {
  const res = await apiClient(`/api/v1/users/${id}/reativar-acesso/`, {
    method: "PATCH",
    signal,
  });
  return res.json();
}

/** Opções de perfil para o filtro (GET /api/v1/roles/). */
export async function fetchRoleOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/roles/?limit=200&ativo=true", {
    signal,
  });
  const data: Paginated<Perfil> = await res.json();
  return data.results.map((r) => ({
    value: String(r.id),
    label: r.nome,
  }));
}

/** Opções de território para o filtro (GET /api/v1/territories/). */
export async function fetchTerritoryOptions(
  signal?: AbortSignal,
): Promise<SelectOption[]> {
  const res = await apiClient("/api/v1/territories/?limit=500", { signal });
  const data: Paginated<Territorio> = await res.json();
  return data.results.map((t) => ({
    value: String(t.id),
    label: t.nome,
  }));
}

// ─── Perfis principais e operacionais (#405, AJ-BE-10) ───────────────────────

export type CategoriaPerfil = "principal" | "operacional";
export type ObjetoTipo = "evento" | "edital" | "candidatura";

/** Espelha `OBJETO_DO_PERFIL_OPERACIONAL` (apps/core/models/user_profile.py). */
export const OBJETO_DO_PERFIL: Record<string, ObjetoTipo> = {
  "coordenador-evento": "evento",
  credenciador: "evento",
  "avaliador-selecao": "candidatura",
  "gestor-edital": "edital",
};

export const OBJETO_TIPO_LABEL: Record<ObjetoTipo, string> = {
  evento: "Evento",
  edital: "Edital",
  candidatura: "Candidatura",
};

/** Perfil sem `categoria` (resposta antiga) conta como principal. */
export function categoriaDoPerfil(perfil: Pick<Perfil, "categoria"> | undefined): CategoriaPerfil {
  return perfil?.categoria === "operacional" ? "operacional" : "principal";
}

/** GET /api/v1/roles/ — os perfis ativos, com a categoria de cada um. */
export async function fetchRoles(signal?: AbortSignal): Promise<Perfil[]> {
  const res = await apiClient("/api/v1/roles/?limit=200&ativo=true", { signal });
  const data: Paginated<Perfil> = await res.json();
  return data.results;
}

export function opcoesDePerfil(perfis: Perfil[], categoria?: CategoriaPerfil | ""): SelectOption[] {
  return perfis
    .filter((p) => !categoria || categoriaDoPerfil(p) === categoria)
    .map((p) => ({ value: String(p.id), label: p.nome }));
}

/** Uma linha de perfil principal do formulário: território vazio = todos. */
export type LinhaPrincipal = { perfil: string; territorio: string };
/** Uma linha de perfil operacional: o objeto é obrigatório. */
export type LinhaOperacional = { perfil: string; objetoId: string };

export type NovoUsuario = {
  nome: string;
  email: string;
  senha: string;
  principais: LinhaPrincipal[];
  operacionais: LinhaOperacional[];
};

/** `PerfilInputSerializer`. */
export type PerfilInput = {
  perfil_id: number;
  territorio_id: number | null;
  objeto_tipo: ObjetoTipo | null;
  objeto_id: number | null;
};

export type ErrosNovoUsuario = {
  nome?: string;
  email?: string;
  principais?: string;
  /** Erro por linha operacional, pelo índice. */
  operacionais?: Record<number, string>;
};

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * As mesmas regras de `validate_perfis_input`, antes do envio: ao menos um
 * perfil principal, operacional sempre com objeto e sem designação repetida.
 */
export function validarNovoUsuario(form: NovoUsuario, perfis: Perfil[]): ErrosNovoUsuario {
  const erros: ErrosNovoUsuario = {};
  if (!form.nome.trim()) erros.nome = "Informe o nome completo.";
  if (!EMAIL.test(form.email.trim())) erros.email = "Informe um e-mail válido.";

  const principais = form.principais.filter((l) => l.perfil);
  if (principais.length === 0) {
    erros.principais = "Escolha ao menos um perfil principal.";
  } else {
    const chaves = principais.map((l) => `${l.perfil}:${l.territorio}`);
    if (new Set(chaves).size !== chaves.length) {
      erros.principais = "O mesmo perfil está repetido no mesmo território.";
    }
  }

  const porLinha: Record<number, string> = {};
  const vistos = new Set<string>();
  form.operacionais.forEach((linha, i) => {
    if (!linha.perfil) {
      porLinha[i] = "Escolha o perfil ou remova a linha.";
      return;
    }
    const perfil = perfis.find((p) => String(p.id) === linha.perfil);
    const tipo = perfil ? OBJETO_DO_PERFIL[perfil.slug] : undefined;
    if (!/^[1-9]\d*$/.test(linha.objetoId.trim())) {
      porLinha[i] = `Informe o número do ${tipo ? OBJETO_TIPO_LABEL[tipo].toLowerCase() : "objeto"}.`;
      return;
    }
    const chave = `${linha.perfil}:${linha.objetoId.trim()}`;
    if (vistos.has(chave)) porLinha[i] = "Este perfil já está designado a este objeto.";
    vistos.add(chave);
  });
  if (Object.keys(porLinha).length > 0) erros.operacionais = porLinha;
  return erros;
}

/** Monta o `perfis_input`: principal leva território (ou nulo), operacional leva o objeto. */
export function montarPerfisInput(form: NovoUsuario, perfis: Perfil[]): PerfilInput[] {
  const principais: PerfilInput[] = form.principais
    .filter((l) => l.perfil)
    .map((l) => ({
      perfil_id: Number(l.perfil),
      territorio_id: l.territorio ? Number(l.territorio) : null,
      objeto_tipo: null,
      objeto_id: null,
    }));
  const operacionais: PerfilInput[] = form.operacionais
    .filter((l) => l.perfil)
    .map((l) => {
      const perfil = perfis.find((p) => String(p.id) === l.perfil);
      return {
        perfil_id: Number(l.perfil),
        territorio_id: null,
        objeto_tipo: (perfil && OBJETO_DO_PERFIL[perfil.slug]) ?? null,
        objeto_id: Number(l.objetoId.trim()),
      };
    });
  return [...principais, ...operacionais];
}

/** POST /api/v1/users/ — cria o usuário com os perfis. A senha é opcional. */
export async function criarUsuario(form: NovoUsuario, perfis: Perfil[]): Promise<UserListItem> {
  const body: Record<string, unknown> = {
    nome_completo: form.nome.trim(),
    email: form.email.trim(),
    perfis_input: montarPerfisInput(form, perfis),
  };
  if (form.senha) body.password = form.senha;
  const res = await apiClient("/api/v1/users/", { method: "POST", body: JSON.stringify(body) });
  return res.json();
}

// ─── Desativação com aviso de impacto (#406, AJ-BE-11) ───────────────────────

/** `ImpactoDesativacaoSerializer`: o que a desativação cancela e libera. */
export type ImpactoDesativacao = {
  demandas: { id: number; titulo: string; status: string; saldo_liberado: string }[];
  saldo_por_rubrica: { rubrica_id: number; rubrica_nome: string; valor: string }[];
  saldo_liberado: string;
};

/** GET /api/v1/core/usuarios/{id}/impacto-desativacao/ — só leitura, não muda nada. */
export async function fetchImpactoDesativacao(
  userId: number,
  signal?: AbortSignal,
): Promise<ImpactoDesativacao> {
  const res = await apiClient(`/api/v1/core/usuarios/${userId}/impacto-desativacao/`, { signal });
  return res.json();
}

/**
 * DELETE /api/v1/users/{id}/ — desativa (não apaga): o backend cancela as
 * demandas ainda não autorizadas da pessoa e libera o saldo que elas reservavam.
 */
export async function desativarUsuario(userId: number): Promise<void> {
  await apiClient(`/api/v1/users/${userId}/`, { method: "DELETE" });
}
