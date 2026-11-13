import { apiClient } from "@/app/lib/api";
import type { Paginada, Refinar, Schema } from "@/app/lib/apiSchema";
import type { Perfil, Territorio } from "@/app/lib/auth/types";
import type { SelectOption } from "@/app/components/ui/Select/Select";

// ─── Tipos ──────────────────────────────────────────────────────────────────

/** Autor de uma revogação — `acesso_revogado_por` do UserListSerializer. */
export type RevogadoPor = Schema<"UsuarioRef">;

/**
 * Um vínculo do usuário (`role_com_objeto`): o perfil e, no operacional, o
 * objeto de abrangência. O principal vem com o objeto nulo.
 */
export type PerfilDoUsuario = Perfil & {
  objeto_tipo?: ObjetoTipo | null;
  objeto_id?: number | null;
};

/**
 * `UserListSerializer`, a partir do schema (#273).
 *
 * Refinamentos: o schema marca como opcionais campos que a resposta sempre
 * traz (`ativo`, `ultimo_login`, `acesso_revogado` e `acesso_revogado_em`), e
 * `perfis` e `territorios` seguem os tipos da sessão (`auth/types.ts`), que
 * ainda não migraram.
 *
 * - `acesso_revogado`: wipe remoto pendente. O app SCA apaga os dados locais no
 *   próximo sync e exige novo login. Independe de `ativo`: um usuário revogado
 *   continua ativo, então não some da listagem default (`ativo=true`).
 * - `qtd_dispositivos` e `ultimo_sync_dispositivos`: só vêm preenchidos com
 *   `?com_dispositivo=true`, para não pagar o N+1 nas demais listagens
 *   (apps/core/views/users.py::UserViewSet.get_queryset).
 */
export type UserListItem = Refinar<
  Schema<"UserList">,
  {
    perfis: PerfilDoUsuario[];
    territorios: Territorio[];
    ativo: boolean;
    ultimo_login: string | null;
    acesso_revogado: boolean;
    acesso_revogado_em: string | null;
  }
>;

/** Resposta paginada padrão do DRF. O nome antigo segue exportado para quem já importa daqui. */
export type Paginated<T> = Paginada<T>;

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
export type AcessoResponse = Schema<"UserAcessoResposta">;

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

export type CategoriaPerfil = Schema<"CategoriaDoPerfilEnum">;
export type ObjetoTipo = Schema<"TipoDoObjetoDoPerfilEnum">;

/**
 * Cópia de `OBJETO_DO_PERFIL_OPERACIONAL` (apps/core/models/user_profile.py):
 * `/roles/` não diz o tipo de objeto de cada perfil operacional. Quando disser
 * (pendência 8 de `docs/pendencias-backend-sprint-12b.md`), sai daqui.
 */
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

/**
 * Chips da coluna Perfis. `perfis` vem um item por vínculo: o principal se
 * repete por território (que tem coluna própria) e vira um chip só; o
 * operacional vira um chip por objeto, com o objeto no rótulo.
 */
export function perfisDaListagem(perfis: PerfilDoUsuario[]): { chave: string; rotulo: string }[] {
  const itens = new Map<string, string>();
  for (const p of perfis) {
    const temObjeto = categoriaDoPerfil(p) === "operacional" && p.objeto_tipo && p.objeto_id != null;
    const chave = temObjeto ? `${p.id}:${p.objeto_tipo}:${p.objeto_id}` : String(p.id);
    if (itens.has(chave)) continue;
    const tipo = temObjeto ? (OBJETO_TIPO_LABEL[p.objeto_tipo as ObjetoTipo] ?? p.objeto_tipo) : "";
    itens.set(chave, temObjeto ? `${p.nome} · ${String(tipo).toLowerCase()} ${p.objeto_id}` : p.nome);
  }
  return Array.from(itens, ([chave, rotulo]) => ({ chave, rotulo }));
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
/** Um item de `perfis_input`: o `PerfilInputRequest` do schema, com os anuláveis sempre enviados. */
export type PerfilInput = Refinar<
  Schema<"PerfilInputRequest">,
  { territorio_id: number | null; objeto_tipo: ObjetoTipo | null; objeto_id: number | null }
>;

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
export type ImpactoDesativacao = Schema<"ImpactoDesativacao">;

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
