"""Helpers para testes que intercalam transações em conexões diferentes."""
import threading
import time

from django.db import connection, transaction


def esperar_alguem_bloqueado(timeout=10):
    """Espera outra conexão ficar parada num lock de linha. Roda na thread do teste, em
    autocommit: cada consulta abre um snapshot novo de `pg_stat_activity`."""
    prazo = time.monotonic() + timeout
    while time.monotonic() < prazo:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()"
            )
            if cursor.fetchone()[0]:
                return
        time.sleep(0.02)
    raise AssertionError("Nenhuma conexão ficou esperando lock.")


def intercalar(segura, espera):
    """`segura(pausa)` roda numa transação e, ao chamar `pausa()`, para com ela aberta.
    Então `espera()` começa em outra conexão; quando `espera()` fica bloqueada num lock,
    `segura` segue e commita. Devolve resultados e exceções nas chaves "segura" e "espera"."""
    pausou, pode_seguir = threading.Event(), threading.Event()
    resultados, erros = {}, {}

    def pausa():
        pausou.set()
        pode_seguir.wait(timeout=10)

    def segurar():
        with transaction.atomic():
            return segura(pausa)

    def rodar(lado, funcao):
        try:
            resultados[lado] = funcao()
        except Exception as exc:
            erros[lado] = exc
        finally:
            pausou.set()
            connection.close()

    thread_segura = threading.Thread(target=rodar, args=("segura", segurar))
    thread_segura.start()
    assert pausou.wait(timeout=10)
    thread_espera = threading.Thread(target=rodar, args=("espera", espera))
    thread_espera.start()
    try:
        esperar_alguem_bloqueado()
    finally:
        pode_seguir.set()
        thread_segura.join(timeout=15)
        thread_espera.join(timeout=15)
    assert not thread_segura.is_alive() and not thread_espera.is_alive()
    return resultados, erros
