#!/usr/bin/env bash
# Diz se o push traz migration que quebra o código anterior: com deploy automático,
# a versão velha roda alguns segundos contra o schema novo, e o rollback por tag
# volta para ela. Nesses casos o deploy automático para e espera o workflow manual.
#
# Uso: migracoes-destrutivas.sh <sha-antes> <sha-depois>
#   MANAGE: comando que roda o manage.py (ex.: "docker run --rm ... python manage.py")
# Escreve destrutiva=true|false em $GITHUB_OUTPUT.
#
# ponytail: olha o SQL do sqlmigrate (DROP TABLE/COLUMN, RENAME, SET NOT NULL).
# RunPython que apaga dado e AddField NOT NULL sem db_default passam sem aviso.
set -euo pipefail

antes=$1
depois=$2
saida="${GITHUB_OUTPUT:-/dev/stdout}"

if ! git cat-file -e "${antes}^{commit}" 2>/dev/null; then
    echo "::warning::Commit anterior ausente (push forçado ou primeiro push): tratado como destrutivo."
    echo "destrutiva=true" >> "$saida"
    exit 0
fi

destrutiva=false
while IFS= read -r arquivo; do
    [ -n "$arquivo" ] || continue
    app=$(cut -d/ -f3 <<<"$arquivo")
    nome=$(basename "$arquivo" .py)
    sql=$($MANAGE sqlmigrate "$app" "$nome" </dev/null)
    if achados=$(grep -Ei 'DROP TABLE|DROP COLUMN|RENAME|SET NOT NULL' <<<"$sql"); then
        echo "::warning file=$arquivo::Migration destrutiva"
        echo "$achados"
        destrutiva=true
    fi
done < <(git diff --name-only --diff-filter=A "$antes" "$depois" -- 'backend/apps/*/migrations/0*.py')

echo "destrutiva=$destrutiva" >> "$saida"
