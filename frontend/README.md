This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Tipos da API (schema OpenAPI)

Os tipos de resposta e de escrita da API não são escritos à mão. Eles saem do schema do backend:

```
backend/schema.yml  ->  npm run gen:api-types  ->  app/lib/api-types.ts
```

`app/lib/api-types.ts` é gerado pelo `openapi-typescript` e fica versionado. Não edite esse arquivo.

### Quando o backend muda

1. O backend regenera o `backend/schema.yml` (ver `backend/README.md`).
2. No `frontend/`, rode `npm run gen:api-types` e commite o `api-types.ts` junto.
3. Rode `npm run typecheck`. Campo removido ou renomeado aparece como erro de compilação nos arquivos que o usam.

### Comandos

| Comando | O que faz |
|---|---|
| `npm run gen:api-types` | Regenera `app/lib/api-types.ts` a partir de `backend/schema.yml`. |
| `npm run check:api-types` | Falha se o `api-types.ts` commitado não for o que o schema gera. |
| `npm run typecheck` | Gera os tipos de rota do Next e compila o projeto (`tsc --noEmit`). |

O workflow `Frontend - tipos da API` roda `check:api-types` e `typecheck` em todo PR que mexe em `frontend/` ou em `backend/schema.yml`.

### Como usar nos arquivos de `app/lib/`

Os tipos de tela são montados a partir do schema, por `app/lib/apiSchema.ts`:

```ts
import type { Refinar, Schema } from "@/app/lib/apiSchema";

// O componente do schema, como veio.
export type AcessoResponse = Schema<"UserAcessoResposta">;

// Quando o schema descreve um campo de forma mais frouxa do que a resposta real.
export type MetaListItem = Refinar<
  Schema<"WorkPlanMetaList">,
  { status_calculado: MetaStatus; criado_por: string | null }
>;
```

- Tipos de escrita se chamam `XRequest` e `PatchedXRequest` no schema.
- `Refinar` só aceita campo que existe no tipo gerado. Cada uso é um débito do schema: o ideal é o backend descrever o campo e o refinamento sair.
- O arquivo é gerado com fim de linha LF em qualquer sistema (`.gitattributes`), porque a checagem compara byte a byte.

### Situação da migração (#273)

| Arquivo | Situação |
|---|---|
| `metas.ts`, `semaforo.ts`, `choices.ts`, `users.ts` | Migrados. |
| `ufpas.ts`, `ufpaDocumentos.ts`, `membros.ts`, `atividades.ts`, `atividadesCalendario.ts`, `producao.ts`, `painel.ts`, `formularios.ts`, `exportarAtividades.ts`, `exportarPlano.ts` | Depois do merge da renomeação para UFPA no backend (PR #417), que muda os nomes no schema. |
| `acoes.ts` | Pendente: o schema exige `submeta` e `indicador` na escrita da Ação, e o formulário ainda envia `meta` e `tipo_unidade`. Precisa de ajuste de tela antes de migrar. |
| `orcamento.ts`, `tecnicos.ts`, `integracoes.ts`, `integracoesPowerBi.ts` | Já podem migrar; ainda não feitos. |
| SGD e SCA (`demandas.ts`, `arlo.ts`, `execucaoSgd.ts`, `sca.ts`, `conflitos.ts`, `solicitacoes.ts`, `remanejamentos.ts`) | Esperam o schema dessas rotas ficar preciso no backend. |

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
