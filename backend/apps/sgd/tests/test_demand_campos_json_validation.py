from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.sgd.services.demand_request import validar_campos_json

pytestmark = pytest.mark.django_db


def _campos_passagem(**overrides):
    campos = {
        "passageiro_nome": "Fulano", "passageiro_cpf": "52998224725",
        "passageiro_data_nascimento": "1990-01-01", "aeroporto_origem": "NAT",
        "aeroporto_destino": "GRU", "data_hora_ida": "2026-06-01T08:00:00Z",
        "ida_e_volta": False, "bagagem_despachada": True, "classe": "economica",
        "urgencia": "normal",
    }
    campos.update(overrides)
    return campos


def test_passagem_ida_e_volta_sem_data_volta_bloqueia(activity_rn):
    campos = _campos_passagem(ida_e_volta=True)
    with pytest.raises(DRFValidationError):
        validar_campos_json("passagem", campos, activity_rn)


def test_passagem_ida_e_volta_com_data_volta_ok(activity_rn):
    campos = _campos_passagem(ida_e_volta=True, data_hora_volta="2026-06-05T20:00:00Z")
    validado = validar_campos_json("passagem", campos, activity_rn)
    assert validado.beneficiario_cpf == "52998224725"


def test_passagem_ida_e_volta_false_nao_exige_data_volta(activity_rn):
    campos = _campos_passagem(ida_e_volta=False)
    validado = validar_campos_json("passagem", campos, activity_rn)
    assert "data_hora_volta" not in validado.campos_json or not validado.campos_json.get("data_hora_volta")


def test_passagem_classe_executiva_sem_justificativa_bloqueia(activity_rn):
    campos = _campos_passagem(classe="executiva")
    with pytest.raises(DRFValidationError):
        validar_campos_json("passagem", campos, activity_rn)


def test_passagem_classe_executiva_com_justificativa_ok(activity_rn):
    campos = _campos_passagem(classe="executiva", justificativa_executiva="Único voo disponível.")
    validado = validar_campos_json("passagem", campos, activity_rn)
    assert validado.campos_json["classe"] == "executiva"


def test_passagem_cpf_invalido_bloqueia(activity_rn):
    campos = _campos_passagem(passageiro_cpf="11111111111")
    with pytest.raises(DRFValidationError):
        validar_campos_json("passagem", campos, activity_rn)


def test_diaria_calcula_numero_diarias_e_valor_total(activity_rn, municipio_rn):
    from django.core.cache import cache

    from apps.core.models.system_config import SystemConfig, TipoConfiguracao

    SystemConfig.objects.update_or_create(
        chave="sgd_valor_diaria_padrao", defaults={"valor": "200", "tipo": TipoConfiguracao.STRING},
    )

    campos = {
        "beneficiario_nome": "Fulano", "beneficiario_cpf": "52998224725",
        "beneficiario_cargo": "Técnico", "beneficiario_vinculo": "servidor_ufersa",
        "municipio_destino_id": municipio_rn.pk, "data_inicio": "2026-06-01", "data_fim": "2026-06-04",
        "meio_transporte": "rodoviario", "justificativa": "Visita técnica.",
    }
    try:
        validado = validar_campos_json("diaria", campos, activity_rn)
        assert validado.campos_json["numero_diarias"] == 3
        assert validado.valor_estimado_auto == Decimal("600")
    finally:
        # Cache de SystemConfig não é transacional — limpa pra não vazar
        # "200" pros testes seguintes.
        cache.delete("system_config:sgd_valor_diaria_padrao")


def test_equipamento_menos_de_3_cotacoes_bloqueia_submissao(demand_rascunho_rn):
    from apps.sgd.services.demand import _exigir_minimo_cotacoes_equipamento
    from apps.sgd.tests.factories import DemandDocumentFactory, DemandRequestFactory

    DemandRequestFactory(demanda=demand_rascunho_rn, tipo="equipamento", campos_json={
        "descricao_equipamento": "Notebook", "especificacao_tecnica_detalhada": "16GB RAM",
        "quantidade": 1, "finalidade_justificativa": "Uso em campo.", "urgencia": "normal",
    })
    DemandDocumentFactory(demanda=demand_rascunho_rn, tipo="cotacao")
    DemandDocumentFactory(demanda=demand_rascunho_rn, tipo="cotacao")

    with pytest.raises(DRFValidationError):
        _exigir_minimo_cotacoes_equipamento(demand_rascunho_rn)


def test_equipamento_com_3_cotacoes_nao_bloqueia(demand_rascunho_rn):
    from apps.sgd.services.demand import _exigir_minimo_cotacoes_equipamento
    from apps.sgd.tests.factories import DemandDocumentFactory, DemandRequestFactory

    DemandRequestFactory(demanda=demand_rascunho_rn, tipo="equipamento", campos_json={
        "descricao_equipamento": "Notebook", "especificacao_tecnica_detalhada": "16GB RAM",
        "quantidade": 1, "finalidade_justificativa": "Uso em campo.", "urgencia": "normal",
    })
    for _ in range(3):
        DemandDocumentFactory(demanda=demand_rascunho_rn, tipo="cotacao")

    _exigir_minimo_cotacoes_equipamento(demand_rascunho_rn)


def test_equipamento_3_cotacoes_do_mesmo_fornecedor_bloqueia(demand_rascunho_rn):
    from apps.sgd.services.demand import _exigir_minimo_cotacoes_equipamento
    from apps.sgd.tests.factories import DemandDocumentFactory, DemandRequestFactory

    DemandRequestFactory(demanda=demand_rascunho_rn, tipo="equipamento", campos_json={
        "descricao_equipamento": "Notebook", "especificacao_tecnica_detalhada": "16GB RAM",
        "quantidade": 1, "finalidade_justificativa": "Uso em campo.", "urgencia": "normal",
    })
    for _ in range(3):
        DemandDocumentFactory(demanda=demand_rascunho_rn, tipo="cotacao", fornecedor="Fornecedor Único Ltda")

    with pytest.raises(DRFValidationError):
        _exigir_minimo_cotacoes_equipamento(demand_rascunho_rn)


def test_rubrica_slug_para_tipo_corresponde_ao_mapeamento_configurado():
    from django.core.cache import cache

    from apps.core.models.system_config import SystemConfig, TipoConfiguracao
    from apps.sgd.services.demand_request import rubrica_slug_para_tipo

    SystemConfig.objects.update_or_create(
        chave="sgd_mapeamento_tipo_rubrica",
        defaults={"valor": '{"diaria": "diarias-teste"}', "tipo": TipoConfiguracao.JSON},
    )
    try:
        assert rubrica_slug_para_tipo("diaria") == "diarias-teste"
    finally:
        # O cache de SystemConfig não é transacional (não é desfeito com o
        # rollback do teste) — sem isso, o mapeamento estreito vaza pros
        # testes seguintes que dependem do default completo.
        cache.delete("system_config:sgd_mapeamento_tipo_rubrica")


def test_atualizar_solicitacao_em_rascunho_permitido(demand_rascunho_rn, municipio_rn):
    from apps.sgd.services.demand import atualizar_solicitacao
    from apps.sgd.tests.factories import DemandRequestFactory

    solicitacao = DemandRequestFactory(
        demanda=demand_rascunho_rn, tipo="grafico", campos_json={
            "tipo_material": "banner", "quantidade": 1,
            "especificacoes_tecnicas": "1x1m", "prazo_entrega": "2026-12-01",
        },
    )

    atualizado = atualizar_solicitacao(solicitacao, campos_json={
        "tipo_material": "banner", "quantidade": 5,
        "especificacoes_tecnicas": "2x2m", "prazo_entrega": "2026-12-15",
    })

    assert atualizado.campos_json["quantidade"] == 5


def test_atualizar_solicitacao_bloqueada_fora_de_rascunho_devolvida(demand_rascunho_rn):
    from apps.sgd.services.demand import atualizar_solicitacao
    from apps.sgd.tests.factories import DemandRequestFactory

    demand_rascunho_rn.status = "autorizada"
    demand_rascunho_rn.save(update_fields=["status"])
    solicitacao = DemandRequestFactory(demanda=demand_rascunho_rn, tipo="grafico", campos_json={
        "tipo_material": "banner", "quantidade": 1,
        "especificacoes_tecnicas": "1x1m", "prazo_entrega": "2026-12-01",
    })

    with pytest.raises(DRFValidationError):
        atualizar_solicitacao(solicitacao, campos_json={"quantidade": 2})


def test_rubrica_slug_para_tipo_sem_mapeamento_configurado_usa_default():
    from django.core.cache import cache

    from apps.core.models.system_config import SystemConfig
    from apps.sgd.services.demand_request import DEFAULT_TIPO_RUBRICA_MAP, rubrica_slug_para_tipo

    # delete() não invalida o cache de SystemConfig (só post_save o faz) —
    # limpa manualmente pra não ler o valor seedado pela migration 0002.
    SystemConfig.objects.filter(chave="sgd_mapeamento_tipo_rubrica").delete()
    cache.delete("system_config:sgd_mapeamento_tipo_rubrica")

    for tipo, slug_esperado in DEFAULT_TIPO_RUBRICA_MAP.items():
        assert rubrica_slug_para_tipo(tipo) == slug_esperado
