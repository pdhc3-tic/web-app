from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import migrations

# Copiado de propósito: migrations não importam código de app que pode mudar.
# Faixas do Anexo I do Decreto 5.992/2006 na redação vigente (Decreto 11.872/2023), que
# substituiu as quatro faixas do anexo de 2009: São Paulo passou à primeira faixa, e Belo
# Horizonte, Fortaleza, Porto Alegre, Recife e Salvador, às demais capitais.
FAIXAS = [
    # nome, ordem, padrão (para onde caem os municípios sem enquadramento), enquadramento explícito
    ("Brasília, Manaus, Rio de Janeiro e São Paulo", 1, None, [
        ("5300108", "Brasília/DF"),
        ("1302603", "Manaus/AM"),
        ("3304557", "Rio de Janeiro/RJ"),
        ("3550308", "São Paulo/SP"),
    ]),
    ("Demais capitais", 2, "capitais", []),
    ("Demais localidades", 3, "demais", []),
]

CONFIGURACOES = [
    ("sgd_diaria_regra_inteira_por_pernoite", "True", "boolean",
     "Diárias: uma diária inteira por pernoite fora da sede (Lei 8.112/1990, art. 58, §1º). "
     "Desligada, conta uma diária inteira por dia corrido."),
    ("sgd_diaria_regra_meia_no_retorno", "True", "boolean",
     "Diárias: meia diária no dia do retorno à sede (Decreto 5.992/2006, art. 2º). Desligada, conta inteira."),
    ("sgd_diaria_regra_meia_sem_pernoite", "True", "boolean",
     "Diárias: meia diária quando o deslocamento não tem pernoite, ida e volta no mesmo dia. "
     "Desligada, conta inteira."),
    ("sgd_diaria_regra_meia_hospedagem_custeada", "True", "boolean",
     "Diárias: meia diária por pernoite com hospedagem custeada por outro meio "
     "(campo hospedagem_custeada da solicitação). Desligada, conta inteira."),
    ("sgd_diaria_adicional_embarque_ativo", "False", "boolean",
     "Diárias: soma o adicional de embarque e desembarque (Decreto 5.992/2006, art. 8º) ao total da solicitação."),
    ("sgd_diaria_adicional_embarque_valor", "95.00", "string",
     "Diárias: valor (R$) do adicional de embarque e desembarque, por solicitação "
     "(Decreto 5.992/2006, art. 8º e Anexo II, na redação do Decreto 12.434/2025)."),
]

HOSPEDAGEM_CUSTEADA = {"type": "boolean", "title": "Hospedagem custeada por outro meio"}

# Ponto de partida até a carga da tabela federal: o valor único vale desde sempre.
INICIO_DA_CONVERSAO = date(2000, 1, 1)


def semear_faixas(Faixa, Enquadramento):
    """Também usada pelos testes com `transaction=True`, que apagam o que a migration semeou."""
    for nome, ordem, padrao, municipios in FAIXAS:
        faixa, _ = Faixa.objects.get_or_create(nome=nome, defaults={"ordem": ordem, "padrao": padrao})
        for codigo_ibge, referencia in municipios:
            Enquadramento.objects.get_or_create(
                codigo_ibge=codigo_ibge, defaults={"faixa": faixa, "nome_referencia": referencia},
            )


def _valor_padrao_atual(SystemConfig):
    config = SystemConfig.objects.filter(chave="sgd_valor_diaria_padrao").first()
    if config is None:
        return None
    try:
        valor = Decimal(str(config.valor).strip())
    except (InvalidOperation, ValueError):
        return None
    return valor if valor > 0 else None


def semear(apps, schema_editor):
    Faixa = apps.get_model("sgd", "FaixaDestinoDiaria")
    Enquadramento = apps.get_model("sgd", "EnquadramentoFaixaDiaria")
    Tabela = apps.get_model("sgd", "TabelaDiaria")
    SystemConfig = apps.get_model("core", "SystemConfig")
    Tipo = apps.get_model("sgd", "TipoSolicitacao")

    semear_faixas(Faixa, Enquadramento)

    valor = _valor_padrao_atual(SystemConfig)
    if valor is not None:
        for faixa in Faixa.objects.all():
            Tabela.objects.create(
                faixa_destino=faixa, categoria_beneficiario="padrao", vigencia_inicio=INICIO_DA_CONVERSAO,
                valor=valor, origem="fgd",
            )

    for chave, valor_config, tipo, descricao in CONFIGURACOES:
        SystemConfig.objects.get_or_create(
            chave=chave, defaults={"valor": valor_config, "tipo": tipo, "descricao": descricao},
        )

    diaria = Tipo.objects.filter(slug="diaria").first()
    if diaria is not None:
        schema = dict(diaria.schema_campos or {})
        propriedades = dict(schema.get("properties") or {})
        propriedades.setdefault("hospedagem_custeada", HOSPEDAGEM_CUSTEADA)
        schema["properties"] = propriedades
        diaria.schema_campos = schema
        diaria.save(update_fields=["schema_campos"])


def remover(apps, schema_editor):
    apps.get_model("sgd", "TabelaDiaria").objects.all().delete()
    apps.get_model("sgd", "EnquadramentoFaixaDiaria").objects.all().delete()
    apps.get_model("sgd", "FaixaDestinoDiaria").objects.all().delete()
    apps.get_model("core", "SystemConfig").objects.filter(chave__in=[c[0] for c in CONFIGURACOES]).delete()
    diaria = apps.get_model("sgd", "TipoSolicitacao").objects.filter(slug="diaria").first()
    if diaria is not None:
        (diaria.schema_campos or {}).get("properties", {}).pop("hospedagem_custeada", None)
        diaria.save(update_fields=["schema_campos"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_perfis_operacionais"),
        ("sgd", "0022_tabela_diarias"),
    ]

    operations = [
        migrations.RunPython(semear, remover),
    ]
