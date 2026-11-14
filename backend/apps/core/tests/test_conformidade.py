"""Convenções obrigatórias de armazenamento: valem para todo modelo novo, sem lista para manter."""
from django.apps import apps
from django.db import connection, models

PREFIXOS_MONETARIOS = ("valor_", "custo_", "saldo_", "renda_")


def _e_monetario(campo) -> bool:
    return campo.name == "valor" or campo.name.startswith(PREFIXOS_MONETARIOS)


def _modelos(*rotulos):
    return [modelo for rotulo in rotulos for modelo in apps.get_app_config(rotulo).get_models()]


def _campos(modelos, tipo):
    return [
        (modelo, campo)
        for modelo in modelos
        for campo in modelo._meta.get_fields()
        if isinstance(campo, tipo)
    ]


def test_orcamento_e_sgd_nao_tem_float_field():
    modelos = [
        modelo for modelo in _modelos("sgp", "sgd")
        if modelo.__module__.startswith(("apps.sgp.budget", "apps.sgd"))
    ]

    assert modelos
    assert _campos(modelos, models.FloatField) == []


def test_campos_monetarios_sao_decimal_de_14_com_2_casas():
    decimais = _campos(_modelos("sgp", "sgd"), models.DecimalField)
    monetarios = [(modelo, campo) for modelo, campo in decimais if _e_monetario(campo)]
    fora_do_padrao = [
        f"{modelo.__name__}.{campo.name} ({campo.max_digits},{campo.decimal_places})"
        for modelo, campo in monetarios
        if (campo.max_digits, campo.decimal_places) != (14, 2)
    ]

    assert ("BudgetTransaction", "valor") in {(modelo.__name__, campo.name) for modelo, campo in monetarios}
    assert fora_do_padrao == []


def test_nenhum_campo_monetario_e_float_ou_inteiro():
    numericos = _campos(_modelos("sgp", "sgd"), (models.FloatField, models.IntegerField))

    assert [
        f"{modelo.__name__}.{campo.name}"
        for modelo, campo in numericos
        if _e_monetario(campo)
    ] == []


def test_engine_e_postgresql():
    assert connection.vendor == "postgresql"
