"""Confere se o papel de banco do runtime está sujeito à RLS.

Superusuário e papéis com BYPASSRLS ignoram todas as políticas, e o dono da
tabela também, a menos que ela tenha FORCE ROW LEVEL SECURITY. As tabelas com
RLS não usam FORCE: as migrations rodam como `postgres` e o runtime como
`app_user` (db/init/01_app_user.sql), que não é dono delas. Este comando falha
se essa premissa não valer para a conexão configurada.

Uso no ambiente de runtime (sem sobrescrever DB_USER):
    python manage.py verificar_papel_rls
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

TABELAS_COM_RLS = (
    "sgp_ufpa",
    "sgd_demand",
    "sgp_budgetpool",
    "sgp_spendinglimit",
    "sgp_budgettransaction",
)


def problemas_do_papel_atual() -> list[str]:
    problemas = []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        papel, superusuario, bypass = cursor.fetchone()
        if superusuario:
            problemas.append(f"O papel {papel} é superusuário e ignora a RLS.")
        if bypass:
            problemas.append(f"O papel {papel} tem BYPASSRLS.")
        cursor.execute(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner)
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = ANY(%s)
            """,
            [list(TABELAS_COM_RLS)],
        )
        for tabela, rls, force, dono in cursor.fetchall():
            if not rls:
                problemas.append(f"A tabela {tabela} está sem RLS habilitada.")
            if dono == papel and not force:
                problemas.append(f"O papel {papel} é dono de {tabela}, que não tem FORCE ROW LEVEL SECURITY.")
    return problemas


class Command(BaseCommand):
    help = "Falha se o papel de banco do runtime não estiver sujeito às políticas RLS."

    def handle(self, *args, **options):
        problemas = problemas_do_papel_atual()
        if problemas:
            raise CommandError("\n".join(problemas))
        self.stdout.write(self.style.SUCCESS("Papel de banco sujeito à RLS."))
