# Storage Cloudflare R2

O backend usa upload direto cliente para storage via URL presignada. Em desenvolvimento, `STORAGE_BACKEND=local` é o padrão; em produção, use `STORAGE_BACKEND=r2`.

## Variáveis

```env
STORAGE_BACKEND=r2
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=pdhc-iii
R2_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
R2_PUBLIC_URL=https://media.pdhc-iii.org
```

Para desenvolvimento local sem R2:

```env
STORAGE_BACKEND=local
MEDIA_URL=/media/
MEDIA_ROOT=media
```

## Criação Do Bucket

1. Acesse Cloudflare Dashboard.
2. Vá em `R2 Object Storage`.
3. Crie o bucket `pdhc-iii`.
4. Em `Settings`, configure o domínio público do bucket ou CNAME usado em `R2_PUBLIC_URL`.

## Credenciais

1. No Cloudflare Dashboard, acesse `R2`.
2. Clique em `Manage R2 API Tokens`.
3. Crie um token com permissão de leitura/escrita no bucket `pdhc-iii`.
4. Copie `Access Key ID`, `Secret Access Key` e o endpoint da conta.
5. Preencha `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` e `R2_ENDPOINT_URL`.

## CORS Do Bucket

Configure CORS no bucket para permitir upload direto do frontend:

```json
[
  {
    "AllowedOrigins": [
      "http://localhost:3000",
      "https://*.vercel.app",
      "https://pdhc.ufersa.edu.br"
    ],
    "AllowedMethods": ["PUT", "HEAD", "GET"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 300
  }
]
```

Ajuste `AllowedOrigins` para os domínios reais de preview e produção do frontend.

## Fluxo Da Foto Da UPF

1. Cliente solicita `POST /api/v1/upfs/{id}/foto/upload-url/` com `filename`, `content_type` e `size`.
2. Backend valida permissão, tipo e tamanho, gera key `upfs/{id}/foto/{uuid}.{ext}` e retorna `{ url, key, expires_in }`.
3. Cliente faz `PUT` do binário diretamente para a URL retornada.
4. Cliente confirma em `POST /api/v1/upfs/{id}/foto/confirm/` com `{ key }`.
5. Backend valida existência com `head_object`, atualiza `upf.foto_url` e remove a foto anterior quando houver.
6. Cliente remove com `DELETE /api/v1/upfs/{id}/foto/`.

## CSP

O backend envia `Content-Security-Policy` com `connect-src` permitindo `*.r2.cloudflarestorage.com` e `R2_PUBLIC_URL`.
