# O autodiscover do Celery importa só este pacote, não os módulos dentro dele.
from apps.core.tasks.notifications import send_email_notification  # noqa: F401
