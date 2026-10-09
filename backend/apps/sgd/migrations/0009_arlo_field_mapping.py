import json

from django.db import migrations, models

CHAVE = "sgd_arlo_mapeamento_campos"

# Duplicado de apps.sgd.services.arlo_mapping de propósito — migrations não
# importam código de app que pode mudar.
FORMATO_POR_CAMPO = {
    "valor_estimado": "moeda", "valor_autorizado": "moeda", "valor_pago": "moeda", "data_pagamento": "data",
}
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


def _formato(campo):
    return FORMATO_POR_CAMPO.get(campo, "texto")


def _snapshot(linhas):
    return {
        "exportacao": [
            {"campo": m.campo_sgd, "coluna": m.coluna_arlo, "formato": m.formato}
            for m in linhas if m.direcao == "exportacao"
        ],
        "importacao": {
            m.campo_sgd: {"coluna": m.coluna_arlo, "formato": m.formato}
            for m in linhas if m.direcao == "importacao"
        },
    }


def migrar_para_model(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    ArloFieldMapping = apps.get_model("sgd", "ArloFieldMapping")
    ArloImport = apps.get_model("sgd", "ArloImport")

    config = SystemConfig.objects.filter(chave=CHAVE).first()
    try:
        mapeamento = json.loads(config.valor) if config else MAPEAMENTO_PADRAO
    except (TypeError, ValueError):
        mapeamento = MAPEAMENTO_PADRAO

    linhas = [
        ArloFieldMapping(
            direcao="exportacao", campo_sgd=item["campo"], coluna_arlo=item["coluna"],
            formato=_formato(item["campo"]), ordem=ordem,
        )
        for ordem, item in enumerate(mapeamento["exportacao"], start=1)
    ] + [
        ArloFieldMapping(
            direcao="importacao", campo_sgd=campo, coluna_arlo=coluna, formato=_formato(campo), ordem=ordem,
        )
        for ordem, (campo, coluna) in enumerate(mapeamento["importacao"].items(), start=1)
    ]
    ArloFieldMapping.objects.bulk_create(linhas)

    # Operações anteriores a esta migration usaram o mapeamento vigente até aqui.
    ArloImport.objects.update(mapeamento_snapshot=_snapshot(linhas))
    SystemConfig.objects.filter(chave=CHAVE).delete()


def restaurar_system_config(apps, schema_editor):
    SystemConfig = apps.get_model("core", "SystemConfig")
    ArloFieldMapping = apps.get_model("sgd", "ArloFieldMapping")

    ativos = list(ArloFieldMapping.objects.filter(ativo=True).order_by("ordem", "pk"))
    mapeamento = {
        "exportacao": [
            {"campo": m.campo_sgd, "coluna": m.coluna_arlo} for m in ativos if m.direcao == "exportacao"
        ],
        "importacao": {m.campo_sgd: m.coluna_arlo for m in ativos if m.direcao == "importacao"},
    }
    SystemConfig.objects.update_or_create(
        chave=CHAVE,
        defaults={
            "valor": json.dumps(mapeamento, ensure_ascii=False),
            "tipo": "json",
            "descricao": (
                "Mapeamento de colunas Arlo <-> SGD (SGD-RF31/RF32): 'exportacao' lista campo do SGD "
                "e nome da coluna no CSV; 'importacao' mapeia campo do SGD para o nome da coluna da "
                "planilha de retorno. Editável pelo Super Admin."
            ),
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sgd", "0008_arlo_import_ip_origem"),
        ("core", "0020_power_bi_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArloFieldMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("direcao", models.CharField(
                    choices=[("exportacao", "Exportação (SGD → Arlo)"), ("importacao", "Importação (Arlo → SGD)")],
                    max_length=12, verbose_name="Direção",
                )),
                ("campo_sgd", models.CharField(max_length=64, verbose_name="Campo do SGD")),
                ("coluna_arlo", models.CharField(max_length=128, verbose_name="Coluna no Arlo")),
                ("formato", models.CharField(
                    choices=[("texto", "Texto"), ("data", "Data"), ("moeda", "Moeda")],
                    default="texto", max_length=8, verbose_name="Formato",
                )),
                ("ordem", models.PositiveIntegerField(default=0, verbose_name="Ordem")),
                ("ativo", models.BooleanField(default=True, verbose_name="Ativo")),
            ],
            options={
                "verbose_name": "Mapeamento de campo Arlo",
                "verbose_name_plural": "Mapeamentos de campos Arlo",
                "ordering": ["direcao", "ordem", "pk"],
                "constraints": [
                    models.UniqueConstraint(fields=("direcao", "campo_sgd"), name="uq_arlo_map_direcao_campo"),
                    models.UniqueConstraint(fields=("direcao", "coluna_arlo"), name="uq_arlo_map_direcao_coluna"),
                ],
            },
        ),
        migrations.AddField(
            model_name="arloimport",
            name="mapeamento_snapshot",
            field=models.JSONField(
                blank=True, default=dict,
                help_text="Cópia do mapeamento Arlo <-> SGD usado nesta operação — alterações posteriores não a afetam.",
                verbose_name="Mapeamento vigente na operação",
            ),
        ),
        migrations.RunPython(migrar_para_model, restaurar_system_config),
    ]
