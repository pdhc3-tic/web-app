import subprocess
import sys

TASKS_DISPARADAS_PELO_BACKEND = [
    "core.tasks.send_email_notification",
    "sgd.tasks.process_arlo_import",
]


def test_worker_registra_as_tasks_que_o_backend_enfileira():
    """Sobe o app do Celery num processo limpo, como o worker faz: no processo
    do pytest os módulos de task já foram importados por outros caminhos e
    esconderiam uma task fora do autodiscover."""
    script = (
        "import django; django.setup()\n"
        "from setup.celery import app\n"
        "app.loader.import_default_modules()\n"
        "print('\\n'.join(app.tasks))\n"
    )
    resultado = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)

    assert resultado.returncode == 0, resultado.stderr
    registradas = set(resultado.stdout.split())
    ausentes = [nome for nome in TASKS_DISPARADAS_PELO_BACKEND if nome not in registradas]
    assert not ausentes, f"Tasks fora do worker: {ausentes}"
