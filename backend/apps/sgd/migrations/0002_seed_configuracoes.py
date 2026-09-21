import json

from django.db import migrations

# Duplicado de apps.sgd.services.demand_request.DEFAULT_TIPO_RUBRICA_MAP de
# propósito — migrations não importam código de app que pode mudar.
MAPEAMENTO_TIPO_RUBRICA = {
    "diaria": "diarias",
    "passagem": "passagens-aereas",
    "veiculo": "locacao-veiculo",
    "grafico": "material-grafico",
    "alimentacao": "alimentacao-refeicoes",
    "equipamento": "equipamentos-capital",
}

CONFIGURACOES = [
    {
        "chave": "sgd_mapeamento_tipo_rubrica",
        "valor": json.dumps(MAPEAMENTO_TIPO_RUBRICA),
        "tipo": "json",
        "descricao": (
            "Mapeamento tipo de solicitação do SGD -> slug de rubrica orçamentária "
            "(SGD-RF05). Editável pelo Super Admin."
        ),
    },
    {
        "chave": "sgd_valor_diaria_padrao",
        "valor": "0",
        "tipo": "string",
        "descricao": (
            "Valor por diária (R$) da tabela MDA vigente, usado no cálculo automático "
            "de solicitações do tipo Diárias (§3.1 do SGD). Editável pelo Super Admin."
        ),
    },
]


def seed_configuracoes(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    for item in CONFIGURACOES:
        SystemConfig.objects.update_or_create(
            chave=item["chave"],
            defaults={"valor": item["valor"], "tipo": item["tipo"], "descricao": item["descricao"]},
        )


def unseed_configuracoes(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    SystemConfig.objects.filter(chave__in=[item["chave"] for item in CONFIGURACOES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sgd", "0001_initial"),
        ("core", "0020_power_bi_token"),
    ]

    operations = [
        migrations.RunPython(seed_configuracoes, unseed_configuracoes),
    ]
