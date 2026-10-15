"""Demandas de demonstração do SGD, usadas pelo `seed_demo` do SGP.

Cada demanda percorre os services reais (submeter, pré-autorizar, autorizar...)
em vez de gravar o status direto: assim as etapas de aprovação, as reservas de
saldo e a trilha de auditoria saem iguais às que a API produz.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from django.db import connection
from django.utils import timezone

from apps.core.models import Territory, UserProfile
from apps.sgd.models import ArloImport, Demand, DemandIndividualLimit, DemandRequest
from apps.sgd.services import approval as approval_service
from apps.sgd.services import demand as demand_service
from apps.sgp.models import Activity, BudgetAllocation, BudgetRubrica

RUBRICA_ALIMENTACAO = "alimentacao-refeicoes"
RUBRICA_GRAFICO = "material-grafico"

LIMITE_INDIVIDUAL = {"PE": Decimal("6000"), "RN": Decimal("3000")}
LIMITE_INDIVIDUAL_GRAFICO = Decimal("2000")
ALOCACAO_TERRITORIAL = Decimal("60000")

# Passa de 5 dias úteis em qualquer janela de 14 dias corridos, feriados à parte.
DIAS_SEM_MOVIMENTACAO = 14


@dataclass(frozen=True)
class _Cenario:
    uf: str
    titulo: str
    atividade: str
    destino: str
    dias_no_status: int = 2
    grafico: bool = False
    excedente: bool = False


# A ordem é fixa: os testes e as specs E2E dependem dos ids resultantes.
CENARIOS = [
    _Cenario("PE", "Almoço da oficina de organização produtiva", "planejado", "rascunho", 1),
    _Cenario(
        "PE", "Material de divulgação do seminário territorial", "agendado", "submetida",
        DIAS_SEM_MOVIMENTACAO, grafico=True,
    ),
    _Cenario("PE", "Lanche do encontro da juventude rural", "agendado", "devolvida", 4),
    _Cenario("RN", "Refeições do dia de campo em unidade demonstrativa", "agendado", "pre_autorizada", 3),
    _Cenario("RN", "Alimentação do intercâmbio entre comunidades", "agendado", "autorizada", 5),
    _Cenario("PE", "Refeições da feira da agricultura familiar", "agendado", "em_atendimento", 6),
    _Cenario("PE", "Coffee break do curso de gestão (já realizado)", "concluido_sem_evidencia", "concluida", 9),
    _Cenario("RN", "Almoço da reunião comunitária", "agendado", "recusada", 7),
    _Cenario("RN", "Refeições da oficina cancelada pelo solicitante", "planejado", "cancelada", 8),
    _Cenario("PE", "Alimentação da visita técnica em andamento", "em_andamento", "submetida", 3),
    # Por último entre os do RN: o excedente estoura o limite individual e
    # bloquearia as submissões seguintes do mesmo solicitante.
    _Cenario(
        "RN", "Alimentação emergencial do mutirão de cisternas", "agendado", "autorizada", 1,
        excedente=True,
    ),
]


def popular_demandas(*, acao, municipios, solicitantes, dominio_demo: str) -> list[Demand]:
    """`municipios` e `solicitantes` são dicionários por sigla de UF."""
    # O seed não passa pelo middleware que fixa o contexto da política RLS de
    # `sgd_demand`; sem isto, rodando como app_user, as demandas ficariam invisíveis.
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.user_role = %s;", ["super-admin"])

    agora = timezone.now()
    aprovadores = _aprovadores(dominio_demo)
    _preparar_saldos(acao, solicitantes)
    demandas = []
    for cenario in CENARIOS:
        demanda = _criar(cenario, acao, municipios[cenario.uf], solicitantes[cenario.uf], aprovadores, agora)
        demandas.append(demanda)
    return demandas


def _aprovadores(dominio_demo: str) -> dict:
    def usuario(slug, uf=None):
        perfis = UserProfile.objects.filter(
            perfil__slug=slug, user__email__endswith=f"@{dominio_demo}",
        )
        if uf:
            perfis = perfis.filter(territorio__estados__contains=[uf])
        return perfis.select_related("user").order_by("pk").first().user

    return {
        "articulador": {uf: usuario("articulador-estadual", uf) for uf in LIMITE_INDIVIDUAL},
        "ugp": usuario("ugp"),
        "fgd": usuario("fgd"),
    }


def _preparar_saldos(acao, solicitantes) -> None:
    """Alocação territorial e limite individual folgados para todo cenário
    passar nas duas travas — o excedente é o único que estoura de propósito."""
    rubricas = {
        slug: BudgetRubrica.objects.get(slug=slug) for slug in (RUBRICA_ALIMENTACAO, RUBRICA_GRAFICO)
    }
    acao.rubricas_previstas.set([rubricas[RUBRICA_ALIMENTACAO]])

    for uf, solicitante in solicitantes.items():
        territorio = Territory.objects.filter(estados__contains=[uf]).first()
        for rubrica in rubricas.values():
            BudgetAllocation.objects.get_or_create(
                meta=acao.meta, rubrica=rubrica, nivel=BudgetAllocation.Nivel.TERRITORIAL,
                territorio=territorio, defaults={"valor_alocado": ALOCACAO_TERRITORIAL},
            )
        DemandIndividualLimit.objects.update_or_create(
            solicitante=solicitante, rubrica=rubricas[RUBRICA_ALIMENTACAO],
            defaults={"valor_limite": LIMITE_INDIVIDUAL[uf]},
        )
        DemandIndividualLimit.objects.update_or_create(
            solicitante=solicitante, rubrica=rubricas[RUBRICA_GRAFICO],
            defaults={"valor_limite": LIMITE_INDIVIDUAL_GRAFICO},
        )


def _atividade(cenario, acao, municipio, solicitante, agora) -> Activity:
    deslocamento = {
        "planejado": timedelta(days=20), "agendado": timedelta(days=12),
        "em_andamento": -timedelta(hours=2), "concluido_sem_evidencia": -timedelta(days=15),
    }[cenario.atividade]
    inicio = agora + deslocamento
    return Activity.objects.create(
        titulo=f"{cenario.titulo} — atividade", tipo_atividade="oficina", acao=acao,
        forma_atuacao="realizacao", tecnico_responsavel=solicitante, municipio=municipio,
        ambito="municipal", data_inicio=inicio, data_fim=inicio + timedelta(hours=6),
        descricao_narrativa="Atividade criada pelo seed de demonstração do SGD.",
        status=cenario.atividade, criado_por=solicitante,
    )


def _alimentacao(agora) -> dict:
    return {
        "tipo_refeicao": "almoco",
        "data_horario_servico": (agora + timedelta(days=12)).isoformat(),
        "numero_pessoas": 40,
    }


def _grafico(agora) -> dict:
    return {
        "tipo_material": "banner",
        "quantidade": 10,
        "especificacoes_tecnicas": "Banner de lona 1,0 x 2,0 m, impressão em quatro cores.",
        "prazo_entrega": (agora + timedelta(days=10)).date().isoformat(),
    }


def _criar(cenario, acao, municipio, solicitante, aprovadores, agora) -> Demand:
    atividade = _atividade(cenario, acao, municipio, solicitante, agora)
    ja_executada = cenario.atividade in {"em_andamento", "concluido_sem_evidencia"}
    demanda = demand_service.criar_demanda(
        titulo=cenario.titulo, activity=atividade, solicitante=solicitante,
        justificativa="Despesa lançada depois da execução da atividade." if ja_executada else "",
    )

    valor = Decimal("1000") if cenario.excedente else Decimal("500")
    demand_service.adicionar_solicitacao(
        demanda, tipo="alimentacao", campos_json=_alimentacao(agora), valor_estimado=valor, ordem=0,
    )
    if cenario.grafico:
        # Fora das rubricas previstas da Ação: dispara o alerta não bloqueante.
        demand_service.adicionar_solicitacao(
            demanda, tipo="grafico", campos_json=_grafico(agora), valor_estimado=Decimal("350"), ordem=1,
        )

    _conduzir(demanda, cenario, solicitante, aprovadores)
    _datar(demanda, cenario, agora)
    demanda.refresh_from_db()
    return demanda


def _conduzir(demanda, cenario, solicitante, aprovadores) -> None:
    destino = cenario.destino
    if destino == "rascunho":
        return
    articulador = aprovadores["articulador"][cenario.uf]
    ugp, fgd = aprovadores["ugp"], aprovadores["fgd"]

    demand_service.submeter_demanda(demanda, usuario=solicitante)
    if destino == "submetida":
        return
    if destino == "devolvida":
        approval_service.devolver(
            demanda, responsavel=articulador,
            justificativa="Detalhe o número de participantes e o local do serviço.",
        )
        return
    if destino == "cancelada":
        demand_service.cancelar_demanda(
            demanda, usuario=solicitante, motivo="A atividade foi reagendada para o próximo trimestre.",
        )
        return

    approval_service.pre_autorizar(demanda, responsavel=articulador)
    if destino == "pre_autorizada":
        return
    if destino == "recusada":
        approval_service.recusar(
            demanda, responsavel=ugp, justificativa="Rubrica sem saldo previsto para o trimestre.",
        )
        return

    if cenario.excedente:
        solicitacao = demanda.solicitacoes.get()
        approval_service.autorizar(
            demanda, responsavel=ugp, ajustes={solicitacao.pk: LIMITE_INDIVIDUAL[cenario.uf] + Decimal("1000")},
            excedente_autorizado=True,
            justificativa="Remanejamento emergencial: mutirão antecipado pela estiagem na região.",
        )
    else:
        approval_service.autorizar(demanda, responsavel=ugp)
    if destino == "autorizada":
        return

    approval_service.atender(demanda, responsavel=fgd)
    if destino == "em_atendimento":
        return

    approval_service.concluir(
        demanda, responsavel=fgd,
        valores_pagos={s.pk: s.valor_autorizado - Decimal("40") for s in demanda.solicitacoes.all()},
    )


def _datar(demanda, cenario, agora) -> None:
    """Datas relativas a `timezone.now()`: `criado_em` e `status_alterado_em` são
    automáticos, então só um UPDATE recua as demandas no tempo."""
    status_alterado_em = agora - timedelta(days=cenario.dias_no_status)
    Demand.objects.filter(pk=demanda.pk).update(
        status_alterado_em=status_alterado_em,
        criado_em=status_alterado_em - timedelta(days=2),
    )


def popular_arlo(*, demandas, dominio_demo: str, media_base_url: str) -> list[ArloImport]:
    """Histórico do Arlo: uma exportação, uma importação sem erros e uma com erros
    por linha. Só o histórico: o arquivo não é gravado e a task de importação não
    roda, porque ela mudaria o status e o saldo das demandas do seed."""
    agora = timezone.now()
    ugp = _aprovadores(dominio_demo)["ugp"]
    recusada = next(d for d in demandas if d.status == "recusada")

    def registrar(posicao, *, tipo, atras, extensao="csv", **campos):
        pasta = "exportacoes" if tipo == ArloImport.Tipo.EXPORTACAO else "importacoes"
        chave = f"arlo/{pasta}/{uuid5(NAMESPACE_URL, f'seed-arlo-{posicao}')}.{extensao}"
        registro = ArloImport.objects.create(
            tipo=tipo, status=ArloImport.Status.CONCLUIDO, arquivo_key=chave,
            arquivo_url=f"{media_base_url}/{chave}", nome_original=chave.rsplit("/", 1)[-1],
            operado_por=ugp, ip_origem="203.0.113.20", **campos,
        )
        # `operado_em` é automático: só um UPDATE recua o registro no tempo.
        ArloImport.objects.filter(pk=registro.pk).update(operado_em=agora - atras)
        return registro

    autorizadas = DemandRequest.objects.filter(demanda__status="autorizada").count()
    return [
        registrar(
            1, tipo=ArloImport.Tipo.EXPORTACAO, atras=timedelta(days=4),
            total_registros=autorizadas, registros_ok=autorizadas,
        ),
        registrar(
            2, tipo=ArloImport.Tipo.IMPORTACAO, atras=timedelta(days=3), total_registros=3, registros_ok=3,
        ),
        registrar(
            3, tipo=ArloImport.Tipo.IMPORTACAO, atras=timedelta(days=1), total_registros=5, registros_ok=3,
            erros_json=[
                {"linha": 4, "erro": "Valor pago em formato inválido: 'R$ abc'.", "campo": "valor_pago"},
                {
                    "linha": 6,
                    "erro": f"Demanda #{recusada.pk} está em status 'recusada' e não aceita pagamento.",
                    "campo": "demanda_id",
                },
            ],
        ),
    ]
