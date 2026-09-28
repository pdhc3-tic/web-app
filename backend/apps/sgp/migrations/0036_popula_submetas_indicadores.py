"""Converte o Plano de Trabalho de dois níveis (Meta → Ação X.Y, unidade em
`tipo_unidade`) para a hierarquia Meta → Submeta → Ação X.Y.Z com Indicador.

- Cada valor de `tipo_unidade` vira um Indicador do catálogo inicial (de-para
  do Relatório de Alterações §8); a UGP ajusta o catálogo depois pela API.
- Cada Meta com Ações ganha a Submeta X.1, com o título e o período da Meta, e
  as Ações passam de X.Y para X.1.Y.
- Ação sem período herda o da Submeta, que passa a ser obrigatório na 0035.

O mapeamento fica aqui, e não importado do app, porque migrations precisam
continuar rodando depois que as constantes antigas deixarem de existir.
"""
from django.db import migrations

# tipo_unidade → (código, nome, unidade de medida, forma de apuração, categoria)
CATALOGO_INICIAL = {
    1: ("IND-SEM", "Seminário", "evento", "contagem_atividades", "formacao"),
    2: ("IND-OFI", "Oficina", "evento", "contagem_atividades", "formacao"),
    3: ("IND-CUR", "Curso / Capacitação", "evento", "contagem_atividades", "formacao"),
    4: ("IND-PLA", "Plano", "plano", "contagem_atividades", "gestao"),
    5: ("IND-REL", "Relatório de pesquisas", "relatorio", "contagem_atividades", "gestao"),
    6: ("IND-INT", "Intercâmbio", "evento", "contagem_atividades", "formacao"),
    7: ("IND-AUD", "Conteúdo audiovisual", "unidade", "contagem_atividades", "outro"),
    8: ("IND-VIS", "Visita técnica", "evento", "contagem_atividades", "assistencia_tecnica"),
    9: ("IND-ENC", "Encontro / Reunião", "evento", "contagem_atividades", "gestao"),
    10: ("IND-UNI", "Unidade implementada", "unidade", "manual", "estruturacao_produtiva"),
    11: ("IND-FAM", "Família atendida", "familia", "soma_ufpas", "assistencia_tecnica"),
    12: ("IND-OUT", "Outro", "outro", "contagem_atividades", "outro"),
}
TIPO_UNIDADE_OUTRO = 12


def para_hierarquia_nova(apps, schema_editor):
    Indicator = apps.get_model("sgp", "Indicator")
    WorkPlanMeta = apps.get_model("sgp", "WorkPlanMeta")
    WorkPlanSubmeta = apps.get_model("sgp", "WorkPlanSubmeta")
    WorkPlanAcao = apps.get_model("sgp", "WorkPlanAcao")

    indicador_por_tipo = {}
    for tipo, (codigo, nome, unidade, forma, categoria) in CATALOGO_INICIAL.items():
        indicador_por_tipo[tipo], _ = Indicator.objects.get_or_create(
            codigo=codigo,
            defaults={
                "nome": nome,
                "unidade_medida": unidade,
                "forma_apuracao": forma,
                "categoria": categoria,
            },
        )

    for meta in WorkPlanMeta.objects.filter(acoes__isnull=False).distinct():
        submeta, _ = WorkPlanSubmeta.objects.get_or_create(
            meta=meta,
            numero=f"{meta.numero}.1",
            defaults={
                "titulo": meta.titulo,
                "data_inicio": meta.data_inicio,
                "data_fim": meta.data_fim,
                "criado_por": meta.criado_por,
            },
        )
        for acao in WorkPlanAcao.objects.filter(meta=meta, submeta__isnull=True):
            _, _, sequencial = acao.numero.partition(".")
            acao.submeta = submeta
            acao.numero = f"{submeta.numero}.{sequencial or acao.pk}"
            acao.indicador = indicador_por_tipo.get(
                acao.tipo_unidade, indicador_por_tipo[TIPO_UNIDADE_OUTRO]
            )
            acao.data_inicio = acao.data_inicio or submeta.data_inicio
            acao.data_fim = acao.data_fim or submeta.data_fim
            acao.save(update_fields=[
                "submeta", "numero", "indicador", "data_inicio", "data_fim",
            ])


def para_hierarquia_antiga(apps, schema_editor):
    Indicator = apps.get_model("sgp", "Indicator")
    WorkPlanSubmeta = apps.get_model("sgp", "WorkPlanSubmeta")
    WorkPlanAcao = apps.get_model("sgp", "WorkPlanAcao")

    tipo_por_codigo = {codigo: tipo for tipo, (codigo, *_resto) in CATALOGO_INICIAL.items()}
    for acao in WorkPlanAcao.objects.select_related("indicador"):
        partes = acao.numero.split(".")
        if len(partes) == 3:
            acao.numero = f"{partes[0]}.{partes[2]}"
        if acao.indicador_id:
            acao.tipo_unidade = tipo_por_codigo.get(acao.indicador.codigo, TIPO_UNIDADE_OUTRO)
        acao.submeta = None
        acao.indicador = None
        acao.save(update_fields=["numero", "tipo_unidade", "submeta", "indicador"])

    WorkPlanSubmeta.objects.all().delete()
    Indicator.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0035_indicator_workplansubmeta"),
    ]

    operations = [
        migrations.RunPython(para_hierarquia_nova, para_hierarquia_antiga),
    ]
