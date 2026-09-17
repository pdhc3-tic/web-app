from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from apps.core.models import SystemConfig, Territory
from apps.sca.models import ConflictLog, SyncDevice, SyncEvent
from apps.sgp.management.commands.seed_demo import DEMO_EMAIL_DOMAIN
from apps.sgp.models import Activity, MembroFamilia, UPF

User = get_user_model()

pytestmark = pytest.mark.django_db


def rodar_seed(reset=False):
    call_command("seed_core")
    opcoes = {"reset": True} if reset else {}
    call_command(
        "seed_demo", "--no-files", "--upfs", "8", "--atividades", "6", **opcoes
    )


def idade_do_sync(device, referencia=None):
    referencia = referencia if referencia is not None else timezone.now()
    return referencia - device.ultimo_sync_em


def limiar_dias():
    return int(SystemConfig.objects.get(chave="sca_sync_alerta_dias").valor)


def usuarios_sca():
    return {
        local: User.objects.get(email=f"{local}@{DEMO_EMAIL_DOMAIN}")
        for local in ("sca.verde", "sca.laranja", "sca.vermelho")
    }


class TestSeedDemoSca:
    def test_dispositivos_nas_quatro_faixas_de_territorios_distintos(self):
        rodar_seed()

        devices = {d.device_id: d for d in SyncDevice.objects.all()}
        assert set(devices) == {
            "dev-seed-verde",
            "dev-seed-laranja",
            "dev-seed-vermelho",
            "dev-seed-revogado",
        }

        limiar = limiar_dias()
        assert idade_do_sync(devices["dev-seed-verde"]) <= timedelta(hours=2)
        idade_laranja = idade_do_sync(devices["dev-seed-laranja"])
        assert timedelta(days=1) < idade_laranja < timedelta(days=limiar)
        assert idade_do_sync(devices["dev-seed-vermelho"]) > timedelta(days=limiar)

        perfis = {
            email: list(user.profiles.values_list("territorio_id", flat=True))
            for email, user in usuarios_sca().items()
        }
        territorios_distintos = {
            tid for ids in perfis.values() for tid in ids if tid is not None
        }
        assert len(territorios_distintos) >= 3

    def test_eventos_cobrem_conexoes_erros_e_periodo_estendido(self):
        rodar_seed()

        eventos = SyncEvent.objects.all()
        assert eventos.count() == 9
        assert set(eventos.values_list("tipo", flat=True)) >= {"push", "pull"}
        conexoes = set(eventos.exclude(tipo_conexao=None).values_list("tipo_conexao", flat=True))
        assert conexoes == {"wifi", "4g", "3g", "2g", "5g", "offline"}

        com_erro = eventos.filter(contagem_erros__gt=0).get()
        assert len(com_erro.erros_detalhes) == com_erro.contagem_erros
        assert all("codigo" in erro for erro in com_erro.erros_detalhes)
        assert eventos.exclude(contagem_erros__gt=0).exists()

        mais_antigo = eventos.order_by("iniciado_em").first()
        mais_recente = eventos.order_by("-iniciado_em").first()
        espalhamento = mais_recente.iniciado_em - mais_antigo.iniciado_em
        assert espalhamento.days >= limiar_dias()
        assert all(e.finalizado_em >= e.iniciado_em for e in eventos)

    def test_conflitos_pendentes_sensiveis_em_estados_distintos_e_resolvido_auto(self):
        rodar_seed()

        conflitos = ConflictLog.objects.all()
        assert conflitos.count() == 3

        pendentes = conflitos.filter(status=ConflictLog.Status.PENDENTE)
        assert pendentes.count() == 2
        assert set(pendentes.values_list("campo", flat=True)) == {
            "titular.cpf",
            "titular.nome_completo",
        }

        for conflito in pendentes:
            assert conflito.campo_sensivel is True
            assert conflito.valor_final is None
            assert conflito.territorio is not None

        pendente_cpf = pendentes.get(campo="titular.cpf")
        pendente_nome = pendentes.get(campo="titular.nome_completo")

        # Par que torna o recorte por território verificável dos dois lados.
        assert pendente_cpf.territorio_id != pendente_nome.territorio_id
        assert set(pendente_cpf.territorio.estados or []).isdisjoint(
            pendente_nome.territorio.estados or []
        )

        resolvido = conflitos.get(
            status=ConflictLog.Status.RESOLVIDO_AUTO,
            campo="whatsapp",
        )
        assert resolvido.campo_sensivel is False
        assert resolvido.valor_final is not None
        assert resolvido.resolvido_em is not None

    def test_badges_de_origem_sca_e_registro_sem_device(self):
        rodar_seed()

        agora = timezone.now()
        upf = UPF.objects.get(device_id="dev-mock-001")
        assert upf.ultima_origem == "sca"
        assert upf.uuid_local is not None
        assert abs((agora - upf.ultimo_sync_em).total_seconds()) <= 3 * 3600

        membro = MembroFamilia.objects.get(device_id="dev-mock-001")
        assert membro.pk == upf.titular_id
        assert membro.ultima_origem == "sca"

        atividade = Activity.objects.get(device_id="dev-mock-001")
        assert atividade.ultima_origem == "sca"
        assert atividade.uuid_local is not None

        assert UPF.objects.filter(device_id="").exclude(pk=upf.pk).exists()

    def test_wipe_remoto_e_usuarios_para_cenarios_da_listagem(self):
        rodar_seed()

        revogado = User.objects.get(acesso_revogado=True)
        assert revogado.email.endswith(f"@{DEMO_EMAIL_DOMAIN}")
        assert not revogado.email.startswith("sca.")
        assert timezone.now() - revogado.acesso_revogado_em >= timedelta(days=9)

        tecnico_verde = User.objects.get(email=f"sca.verde@{DEMO_EMAIL_DOMAIN}")
        assert tecnico_verde.acesso_revogado is False
        assert tecnico_verde.is_superuser is False
        assert tecnico_verde.sca_devices.filter(ativo=True).exists()


class TestSeedDemoDatasRelativas:
    def test_faixas_seguem_o_relogio_em_execucoes_distintas(self):
        futuro = timezone.make_aware(datetime(2031, 5, 10, 12, 0))
        with patch("django.utils.timezone.now", return_value=futuro):
            rodar_seed()

        limiar = limiar_dias()
        vermelho = SyncDevice.objects.get(device_id="dev-seed-vermelho")
        idade = futuro - vermelho.ultimo_sync_em
        assert idade > timedelta(days=limiar)
        assert idade < timedelta(days=limiar * 3)

        laranja = SyncDevice.objects.get(device_id="dev-seed-laranja")
        idade_laranja = futuro - laranja.ultimo_sync_em
        assert timedelta(days=1) < idade_laranja < timedelta(days=limiar)

        outro_relogio = futuro + timedelta(days=400)
        with patch("django.utils.timezone.now", return_value=outro_relogio):
            rodar_seed(reset=True)

        vermelho = SyncDevice.objects.get(device_id="dev-seed-vermelho")
        idade_nova = outro_relogio - vermelho.ultimo_sync_em
        assert idade_nova > timedelta(days=limiar)
        assert Territory.objects.count() > 0
