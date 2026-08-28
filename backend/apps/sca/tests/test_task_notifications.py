import pytest

from apps.core.models.notifications import Notification, TipoNotificacao
from apps.sca.tasks import notify_articulador_sync_conflict


@pytest.mark.django_db
class TestNotifyArticuladorSyncConflict:
    def test_cria_notification_com_link_do_conflito(self, articulador):
        notify_articulador_sync_conflict(
            articulador.pk,
            conflict_id=42,
            entidade="upf",
            uuid_local="8f14e45f-ea0a-4b1c-9c2f-0f5a7d3b9e01",
            campo="titular.cpf",
            valor_local="33355588800",
            valor_servidor="52998224725",
            territorio_id=1,
        )

        notification = Notification.objects.get(user=articulador)
        assert notification.link == "/sca/conflitos/42"
        assert notification.modulo_origem == "sca"
        assert notification.evento == "sca.sync.conflict_sensitive"
        assert notification.tipo == TipoNotificacao.IN_APP

    def test_sem_conflict_id_link_cai_na_fila_geral(self, articulador):
        notify_articulador_sync_conflict(articulador.pk, entidade="upf", campo="whatsapp")

        notification = Notification.objects.get(user=articulador)
        assert notification.link == "/sca/conflitos"

    def test_usuario_inexistente_nao_gera_notification(self, db):
        notify_articulador_sync_conflict(999999, conflict_id=1)

        assert Notification.objects.count() == 0
