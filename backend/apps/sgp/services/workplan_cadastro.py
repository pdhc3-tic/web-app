"""Regras de cadastro do Plano de Trabalho que vão além da validação de um
único registro: Indicador em uso, recálculo ao trocar a forma de apuração e
Ações que acompanham a Submeta quando ela muda de número ou de Meta."""

from django.db import transaction
from rest_framework import status

from apps.core.services.audit import log_audit
from apps.sgp.exceptions import ErroComCodigo
from apps.sgp.services.apuracao import recalcular_quantidade_realizada


def _snapshot_indicador(indicador) -> dict:
    return {
        "codigo": indicador.codigo,
        "nome": indicador.nome,
        "unidade_medida": indicador.unidade_medida,
        "forma_apuracao": indicador.forma_apuracao,
        "categoria": indicador.categoria,
        "ods_ids": indicador.ods_ids,
        "desagregacoes": indicador.desagregacoes,
        "ativo": indicador.ativo,
    }


def _snapshot_acao(acao) -> dict:
    return {
        "meta_id": acao.meta_id,
        "submeta_id": acao.submeta_id,
        "indicador_id": acao.indicador_id,
        "numero": acao.numero,
        "descricao": acao.descricao,
        "quantidade_planejada": str(acao.quantidade_planejada),
        "quantidade_realizada": acao.quantidade_realizada,
        "valor_unitario": str(acao.valor_unitario),
        "data_inicio": str(acao.data_inicio),
        "data_fim": str(acao.data_fim),
    }


def _snapshot_submeta(submeta) -> dict:
    return {
        "meta_id": submeta.meta_id,
        "numero": submeta.numero,
        "titulo": submeta.titulo,
        "descricao": submeta.descricao,
        "data_inicio": str(submeta.data_inicio),
        "data_fim": str(submeta.data_fim),
        "responsavel_id": submeta.responsavel_id,
    }


@transaction.atomic
def criar_indicador(serializer, *, request):
    serializer.validated_data.pop("confirmar_recalculo", None)
    indicador = serializer.save(criado_por=request.user)
    log_audit(
        user=request.user, acao="Indicator.create", modulo="sgp", entidade="Indicator",
        entidade_id=indicador.pk, valores_novos=_snapshot_indicador(indicador), request=request,
    )
    return indicador


@transaction.atomic
def atualizar_indicador(serializer, *, request):
    """Trocar a forma de apuração de um Indicador com Ações recalcula as
    quantidades já reportadas (SGP §5.4), então exige confirmação explícita."""
    indicador = serializer.instance
    antes = _snapshot_indicador(indicador)
    confirmado = serializer.validated_data.pop("confirmar_recalculo", False)
    nova_forma = serializer.validated_data.get("forma_apuracao", indicador.forma_apuracao)
    troca_forma = nova_forma != indicador.forma_apuracao
    total_acoes = indicador.acoes.count()

    if troca_forma and total_acoes and not confirmado:
        raise ErroComCodigo(
            "confirmacao_necessaria",
            f"Trocar a forma de apuração recalcula a quantidade realizada de {total_acoes} "
            "Ação(ões). Reenvie com confirmar_recalculo=true para confirmar.",
            status_code=status.HTTP_409_CONFLICT,
        )

    indicador = serializer.save()
    if troca_forma:
        recalcular_quantidade_realizada(indicador.acoes.values_list("pk", flat=True))
    log_audit(
        user=request.user,
        acao="Indicator.forma_apuracao_alterada" if troca_forma else "Indicator.update",
        modulo="sgp", entidade="Indicator", entidade_id=indicador.pk,
        valores_anteriores=antes, valores_novos=_snapshot_indicador(indicador), request=request,
    )
    return indicador


@transaction.atomic
def excluir_indicador(indicador, *, request):
    if indicador.acoes.exists():
        raise ErroComCodigo(
            "indicador_em_uso",
            "Indicador vinculado a Ações não pode ser excluído; inative-o.",
            status_code=status.HTTP_409_CONFLICT,
        )
    log_audit(
        user=request.user, acao="Indicator.delete", modulo="sgp", entidade="Indicator",
        entidade_id=indicador.pk, valores_anteriores=_snapshot_indicador(indicador),
        request=request,
    )
    indicador.delete()


@transaction.atomic
def criar_submeta(serializer, *, request):
    submeta = serializer.save(criado_por=request.user)
    log_audit(
        user=request.user, acao="WorkPlanSubmeta.create", modulo="sgp",
        entidade="WorkPlanSubmeta", entidade_id=submeta.pk,
        valores_novos=_snapshot_submeta(submeta), request=request,
    )
    return submeta


@transaction.atomic
def atualizar_submeta(serializer, *, request):
    submeta = serializer.instance
    antes = _snapshot_submeta(submeta)
    submeta = serializer.save()

    # As Ações carregam o número da Submeta como prefixo e a Meta como campo
    # derivado; as duas coisas acompanham a Submeta.
    if submeta.numero != antes["numero"] or submeta.meta_id != antes["meta_id"]:
        for acao in submeta.acoes.all():
            sequencial = acao.numero.rsplit(".", 1)[-1]
            acao.numero = f"{submeta.numero}.{sequencial}"
            acao.save(update_fields=["numero", "submeta"])

    log_audit(
        user=request.user, acao="WorkPlanSubmeta.update", modulo="sgp",
        entidade="WorkPlanSubmeta", entidade_id=submeta.pk, valores_anteriores=antes,
        valores_novos=_snapshot_submeta(submeta), request=request,
    )
    return submeta


@transaction.atomic
def excluir_submeta(submeta, *, request):
    if submeta.acoes.exists():
        raise ErroComCodigo(
            "submeta_com_acoes",
            "Não é possível excluir esta Submeta: existem Ações vinculadas a ela.",
            status_code=status.HTTP_409_CONFLICT,
        )
    log_audit(
        user=request.user, acao="WorkPlanSubmeta.delete", modulo="sgp",
        entidade="WorkPlanSubmeta", entidade_id=submeta.pk,
        valores_anteriores=_snapshot_submeta(submeta), request=request,
    )
    submeta.delete()


@transaction.atomic
def criar_acao(serializer, *, request):
    acao = serializer.save()
    log_audit(
        user=request.user, acao="WorkPlanAcao.create", modulo="sgp", entidade="WorkPlanAcao",
        entidade_id=acao.pk, valores_novos=_snapshot_acao(acao), request=request,
    )
    return acao


@transaction.atomic
def atualizar_acao(serializer, *, request):
    acao = serializer.instance
    antes = _snapshot_acao(acao)
    acao = serializer.save()
    # A quantidade realizada depende da forma de apuração do Indicador: trocar o
    # Indicador (inclusive saindo da forma manual) muda a regra da contagem.
    if acao.indicador_id != antes["indicador_id"]:
        recalcular_quantidade_realizada([acao.pk])
        acao.refresh_from_db(fields=["quantidade_realizada"])
    log_audit(
        user=request.user, acao="WorkPlanAcao.update", modulo="sgp", entidade="WorkPlanAcao",
        entidade_id=acao.pk, valores_anteriores=antes, valores_novos=_snapshot_acao(acao),
        request=request,
    )
    return acao
