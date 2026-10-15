import json

from django.db import migrations

CHAVE = "sgd_arlo_mapeamento_campos"

# Duplicado de apps.sgd.services.arlo_mapping.MAPEAMENTO_PADRAO de propósito —
# migrations não importam código de app que pode mudar.
MAPEAMENTO_PADRAO = {
    "exportacao": [
        {"campo": "demanda_id", "coluna": "ID Demanda"},
        {"campo": "solicitacao_id", "coluna": "ID Solicitação"},
        {"campo": "titulo", "coluna": "Título"},
        {"campo": "meta", "coluna": "Meta"},
        {"campo": "submeta", "coluna": "Submeta"},
        {"campo": "acao", "coluna": "Ação"},
        {"campo": "indicador", "coluna": "Indicador"},
        {"campo": "atividade", "coluna": "Atividade"},
        {"campo": "rubrica", "coluna": "Rubrica"},
        {"campo": "valor_autorizado", "coluna": "Valor Autorizado"},
    ],
    "importacao": {
        "demanda_id": "ID Demanda",
        "solicitacao_id": "ID Solicitação",
        "numero_processo": "Número do Processo",
        "data_pagamento": "Data do Pagamento",
        "valor_pago": "Valor Pago",
        "comprovante": "Comprovante",
    },
}


def seed_mapeamento(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    SystemConfig.objects.update_or_create(
        chave=CHAVE,
        defaults={
            "valor": json.dumps(MAPEAMENTO_PADRAO, ensure_ascii=False),
            "tipo": "json",
            "descricao": (
                "Mapeamento de colunas Arlo <-> SGD (SGD-RF31/RF32): 'exportacao' lista campo do SGD "
                "e nome da coluna no CSV; 'importacao' mapeia campo do SGD para o nome da coluna da "
                "planilha de retorno. Editável pelo Super Admin."
            ),
        },
    )


def unseed_mapeamento(apps, schema_editor):
    apps.get_model("core", "SystemConfig").objects.filter(chave=CHAVE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sgd", "0006_arlo_glosa_risk"),
        ("core", "0020_power_bi_token"),
    ]

    operations = [
        migrations.RunPython(seed_mapeamento, unseed_mapeamento),
    ]
