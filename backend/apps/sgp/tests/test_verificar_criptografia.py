import re

import pytest
from django.core.management import CommandError, call_command
from django.db import connection


@pytest.mark.django_db
def test_conta_e_falha_com_valor_que_nao_decifra(membro, capsys):
    membro.saude = [1, 2]
    membro.cor_raca = 1
    membro.save()

    call_command("verificar_criptografia")
    saida = capsys.readouterr().out
    assert re.search(r"sgp_membrofamilia\.cor_raca: (\d+)/\1 decifram", saida)
    assert "Todos os valores criptografados decifram." in saida

    with connection.cursor() as cursor:
        cursor.execute("UPDATE sgp_membrofamilia SET cor_raca = 'lixo' WHERE id = %s", [membro.pk])
    with pytest.raises(CommandError, match="1 valor"):
        call_command("verificar_criptografia")
