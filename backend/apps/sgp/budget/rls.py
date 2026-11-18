"""RLS do orçamento: protege o que as views leem. O motor age em nome de outra pessoa (a FGD conclui
a demanda do técnico, o sistema cancela a de todos), e sem visão total não acharia a linha a travar.
Quem autoriza a operação continua sendo o serviço que a chama.

A elevação vale só para as políticas que leem `app.user_role` (orçamento e sgd_demand). A de
`sgp_ufpa` resolve o escopo pelo `app.current_user_id`, então `visao_total()` não amplia o acesso a
UFPAs; quando uma operação de sistema precisa delas, usa `apps.core.db_context.acesso_de_sistema_ufpa`."""
from contextlib import contextmanager
from functools import wraps

from django.db import connection, transaction


@contextmanager
def visao_total():
    """O papel anterior volta no fim porque `set_config(..., true)` vale até o fim da transação
    externa, não só do savepoint. Se o bloco falhar, o rollback do savepoint já o desfaz."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.user_role', true)")
            anterior = cursor.fetchone()[0] or ""
            cursor.execute("SELECT set_config('app.user_role', 'super-admin', true)")
        yield
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.user_role', %s, true)", [anterior])


def com_visao_total(funcao):
    @wraps(funcao)
    def executar(*args, **kwargs):
        with visao_total():
            return funcao(*args, **kwargs)
    return executar
