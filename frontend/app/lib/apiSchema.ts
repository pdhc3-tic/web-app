import type { components } from "./api-types";

/**
 * Tipos da API a partir do schema OpenAPI (#273).
 *
 * `api-types.ts` é gerado de `backend/schema.yml` (`npm run gen:api-types`) e
 * não se edita à mão. Os arquivos de `app/lib/` montam os tipos de tela a
 * partir dele, por aqui: campo removido ou renomeado no backend passa a ser
 * erro de compilação, e não um `undefined` na tela.
 */
export type Schemas = components["schemas"];

/** Um componente do schema pelo nome: `Schema<"WorkPlanMetaList">`. */
export type Schema<Nome extends keyof Schemas> = Schemas[Nome];

/**
 * Ajusta campos que o schema descreve de forma mais frouxa do que a resposta
 * real (ex.: `status_calculado: string` em vez do enum).
 *
 * Só aceita campo que existe no tipo gerado. Se o backend remover o campo, o
 * refinamento deixa de compilar junto com o resto. Cada uso é um débito do
 * schema: o ideal é o backend descrever o campo e o refinamento sair.
 */
export type Refinar<T, R extends { [K in keyof R]: K extends keyof T ? unknown : never }> = Omit<T, keyof R> & R;

/** Resposta paginada do DRF (`LimitOffsetPagination` e `PageNumberPagination`). */
export type Paginada<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
