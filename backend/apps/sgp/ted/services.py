import re
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Prefetch
from rest_framework.exceptions import APIException
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.core.services.audit import log_audit
from apps.core.storage import StorageObjectNotFound, get_storage
from apps.sgp.budget.rls import visao_total
from apps.sgp.models import (
    TED,
    BudgetPool,
    TEDVersion,
    TEDVersionRubrica,
    WorkPlanAcao,
    WorkPlanMeta,
    WorkPlanSubmeta,
)

ZERO = Decimal("0")
CENTAVO = Decimal("0.01")
TRAVA_DO_CADASTRO_DO_TED = "sgp_ted_cadastro"
CONTENT_TYPE_DO_DOCUMENTO = "application/pdf"
TAMANHO_MAXIMO_DO_DOCUMENTO = 10 * 1024 * 1024
PADRAO_DA_CHAVE_DO_DOCUMENTO = re.compile(r"^ted/documentos/[0-9a-f-]{36}\.pdf$")


class StorageIndisponivel(APIException):
    status_code = 503
    default_detail = "Não foi possível confirmar o documento no armazenamento. Tente de novo."
    default_code = "storage_indisponivel"


def ted_atual() -> TED | None:
    """Leitura sem trava, para quem só precisa saber a versão vigente."""
    return TED.objects.select_related("versao_vigente").order_by("pk").first()


def travar_ted(pk: int | None = None) -> TED | None:
    """Primeira trava de quem grava o pool nacional ou registra versão, antes de
    qualquer pool. Fica até o commit: o registro de uma versão nova espera, e não
    aprova um teto menor do que o pool que está sendo gravado.

    Sem `select_related`: quem espera a trava recebe a linha do TED relida, mas uma
    tabela juntada no mesmo SELECT vem da foto anterior à espera, e a versão vigente
    nova sairia vazia. A versão é lida depois, já com a trava."""
    teds = TED.objects.select_for_update(no_key=True).order_by("pk")
    return (teds.filter(pk=pk) if pk is not None else teds).first()


def _exigir_dentro_do_teto_nacional(ted: TED | None, *, rubrica, valor: Decimal, campo: str) -> TEDVersion:
    if ted is None or ted.versao_vigente_id is None:
        raise DRFValidationError({campo: "Cadastre o TED antes de distribuir a dotação nacional."})
    versao = ted.versao_vigente
    aprovado = (
        TEDVersionRubrica.objects.filter(versao=versao, rubrica=rubrica)
        .values_list("valor_aprovado", flat=True).first()
    )
    aprovado = aprovado if aprovado is not None else ZERO
    if valor > aprovado:
        raise DRFValidationError({
            campo: (
                f"Excede o valor aprovado no TED para a rubrica {rubrica.nome}: "
                f"R$ {aprovado} na versão {versao.numero_versao}."
            ),
        })
    return versao


def versao_do_pool(ted: TED | None, *, nivel: str, rubrica, novo_valor: Decimal,
                   valor_atual: Decimal | None = None, campo: str = "valor_alocado") -> TEDVersion | None:
    """Versão do TED que o pool grava ao ter o valor definido. No nacional, um valor
    novo, ou maior que o atual, precisa caber no aprovado da rubrica. Reduzir passa
    mesmo sem TED. Quem grava o nacional passa o TED de `travar_ted`."""
    aumenta = valor_atual is None or novo_valor > valor_atual
    if nivel == BudgetPool.Nivel.NACIONAL and aumenta:
        return _exigir_dentro_do_teto_nacional(ted, rubrica=rubrica, valor=novo_valor, campo=campo)
    return ted.versao_vigente if ted is not None and ted.versao_vigente_id else None


def erro_no_documento(content_type: str, tamanho: int) -> tuple[str, str] | None:
    """O campo do pedido de upload que falhou e a mensagem."""
    if content_type != CONTENT_TYPE_DO_DOCUMENTO:
        return "content_type", "O documento do TED precisa ser um PDF."
    if tamanho > TAMANHO_MAXIMO_DO_DOCUMENTO:
        return "size", "O documento excede o tamanho máximo de 10 MB."
    return None


def conferir_documento(key: str) -> None:
    """Consulta o storage fora de qualquer trava: é uma chamada de rede."""
    if not PADRAO_DA_CHAVE_DO_DOCUMENTO.match(key or ""):
        raise DRFValidationError({"documento_key": "Chave de upload inválida."})
    try:
        metadata = get_storage().head_object(key)
    except StorageObjectNotFound:
        raise DRFValidationError({
            "documento_key": "Upload do documento não confirmado. Envie o PDF de novo.",
        })
    except Exception as exc:
        raise StorageIndisponivel() from exc
    erro = erro_no_documento(
        metadata.get("ContentType") or CONTENT_TYPE_DO_DOCUMENTO, metadata.get("ContentLength") or 0,
    )
    if erro:
        raise DRFValidationError({"documento_key": erro[1]})


def gerar_snapshot_do_plano() -> dict:
    """Metas, Submetas e Ações como estão no momento do registro da versão."""
    acoes = WorkPlanAcao.objects.select_related("indicador").prefetch_related("rubricas_previstas")
    metas = WorkPlanMeta.objects.order_by("numero").prefetch_related(
        Prefetch("submetas", queryset=WorkPlanSubmeta.objects.prefetch_related(
            Prefetch("acoes", queryset=acoes),
        )),
    )
    return {
        "metas": [
            {
                "numero": meta.numero,
                "titulo": meta.titulo,
                "data_inicio": meta.data_inicio.isoformat(),
                "data_fim": meta.data_fim.isoformat(),
                "submetas": [
                    {
                        "numero": submeta.numero,
                        "titulo": submeta.titulo,
                        "data_inicio": submeta.data_inicio.isoformat(),
                        "data_fim": submeta.data_fim.isoformat(),
                        "acoes": [
                            {
                                "numero": acao.numero,
                                "descricao": acao.descricao,
                                "indicador": {
                                    "codigo": acao.indicador.codigo,
                                    "nome": acao.indicador.nome,
                                    "unidade_medida": acao.indicador.unidade_medida,
                                },
                                "quantidade_planejada": str(acao.quantidade_planejada),
                                "valor_unitario": str(acao.valor_unitario),
                                "valor_total": str(acao.valor_total.quantize(CENTAVO)),
                                "data_inicio": acao.data_inicio.isoformat(),
                                "data_fim": acao.data_fim.isoformat(),
                                "rubricas_previstas": sorted(r.slug for r in acao.rubricas_previstas.all()),
                            }
                            for acao in submeta.acoes.all()
                        ],
                    }
                    for submeta in meta.submetas.all()
                ],
            }
            for meta in metas
        ],
    }


def _exigir_distribuicao_igual_ao_global(rubricas: list[dict], valor_global: Decimal) -> None:
    soma = sum((item["valor_aprovado"] for item in rubricas), ZERO)
    if soma != valor_global:
        raise DRFValidationError({
            "rubricas": (
                f"A soma das rubricas (R$ {soma}) precisa ser igual ao valor global (R$ {valor_global})."
            ),
        })


def _travar_pools() -> list[BudgetPool]:
    """Todos os pools, em ordem de rubrica e pk, depois do TED: é a ordem de quem
    move saldo. Com eles travados, nenhum pool nacional muda entre a conferência
    contra o novo aprovado e a troca de versão."""
    with visao_total():
        return list(
            BudgetPool.objects.select_for_update(of=("self",)).select_related("rubrica")
            .order_by("rubrica_id", "pk")
        )


def _exigir_pools_nacionais_dentro(pools: list[BudgetPool], rubricas: list[dict]) -> None:
    aprovado = {item["rubrica"].pk: item["valor_aprovado"] for item in rubricas}
    acima = [
        f"{pool.rubrica.nome}: o pool nacional tem R$ {pool.valor_alocado}, acima dos "
        f"R$ {aprovado.get(pool.rubrica_id, ZERO)} desta versão."
        for pool in pools
        if pool.nivel == BudgetPool.Nivel.NACIONAL and pool.valor_alocado > aprovado.get(pool.rubrica_id, ZERO)
    ]
    if acima:
        raise DRFValidationError({
            "rubricas": acima + ["Reduza o pool nacional dessas rubricas antes de registrar a versão."],
        })


def _registrar(ted: TED, *, tipo: str, motivo: str, vigencia_inicio, vigencia_fim,
               valor_global: Decimal, rubricas: list[dict], documento_key: str,
               usuario, request=None) -> TEDVersion:
    anterior = ted.versao_vigente
    if tipo == TEDVersion.Tipo.PRORROGACAO and anterior is not None and vigencia_fim <= anterior.vigencia_fim:
        raise DRFValidationError({
            "vigencia_fim": (
                f"A prorrogação precisa estender o fim da vigência, hoje em "
                f"{anterior.vigencia_fim.strftime('%d/%m/%Y')}."
            ),
        })
    _exigir_distribuicao_igual_ao_global(rubricas, valor_global)
    if TEDVersion.objects.filter(documento_key=documento_key).exists():
        raise DRFValidationError({
            "documento_key": "Este PDF já está em outra versão do TED. Envie o documento deste termo.",
        })
    pools = _travar_pools()
    _exigir_pools_nacionais_dentro(pools, rubricas)

    numero = (anterior.numero_versao + 1) if anterior is not None else 1
    versao = TEDVersion.objects.create(
        ted=ted, numero_versao=numero, tipo=tipo, motivo=motivo,
        vigencia_inicio=vigencia_inicio, vigencia_fim=vigencia_fim, valor_global=valor_global,
        plano_snapshot=gerar_snapshot_do_plano(), documento_key=documento_key, registrado_por=usuario,
    )
    TEDVersionRubrica.objects.bulk_create([
        TEDVersionRubrica(versao=versao, rubrica=item["rubrica"], valor_aprovado=item["valor_aprovado"])
        for item in rubricas
    ])

    ted.versao_vigente = versao
    ted.valor_global = valor_global
    ted.vigencia_inicio = vigencia_inicio
    ted.vigencia_fim = vigencia_fim
    ted.save(update_fields=["versao_vigente", "valor_global", "vigencia_inicio", "vigencia_fim"])
    with visao_total():
        BudgetPool.objects.filter(pk__in=[pool.pk for pool in pools]).update(ted_versao=versao)

    log_audit(
        user=usuario, acao="TEDVersion.create", modulo="sgp", entidade="TEDVersion",
        entidade_id=versao.pk, request=request,
        valores_novos={
            "ted_id": ted.pk, "numero_versao": numero, "tipo": tipo, "motivo": motivo,
            "vigencia_inicio": vigencia_inicio.isoformat(), "vigencia_fim": vigencia_fim.isoformat(),
            "valor_global": str(valor_global), "documento_key": documento_key,
            "rubricas": {item["rubrica"].slug: str(item["valor_aprovado"]) for item in rubricas},
        },
    )
    return versao


def cadastrar_ted(*, numero: str, participes: list[str], objeto: str, versao: dict,
                  usuario, request=None) -> TED:
    """O TED nasce com a versão original. O projeto tem um TED só: aditivos e
    prorrogações entram como versões dele."""
    conferir_documento(versao["documento_key"])
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [TRAVA_DO_CADASTRO_DO_TED])
        if TED.objects.exists():
            raise DRFValidationError({
                "numero": "Já existe um TED cadastrado. Registre aditivos e prorrogações como novas versões.",
            })
        ted = TED.objects.create(numero=numero, participes=participes, objeto=objeto)
        log_audit(
            user=usuario, acao="TED.create", modulo="sgp", entidade="TED", entidade_id=ted.pk,
            valores_novos={"numero": numero, "participes": participes, "objeto": objeto}, request=request,
        )
        _registrar(ted, tipo=TEDVersion.Tipo.ORIGINAL, usuario=usuario, request=request, **versao)
    return ted


def registrar_versao(ted: TED, *, versao: dict, usuario, request=None) -> TEDVersion:
    if versao["tipo"] == TEDVersion.Tipo.ORIGINAL:
        raise DRFValidationError({"tipo": "A versão original é registrada junto com o TED."})
    conferir_documento(versao["documento_key"])
    with transaction.atomic():
        ted = travar_ted(ted.pk)
        return _registrar(ted, usuario=usuario, request=request, **versao)


@transaction.atomic
def atualizar_ted(ted: TED, *, dados: dict, usuario, request=None) -> TED:
    """Só a identificação: valores e vigência mudam por nova versão."""
    ted = travar_ted(ted.pk)
    campos = [campo for campo in ("numero", "participes", "objeto") if campo in dados]
    if not campos:
        return ted
    antes = {campo: getattr(ted, campo) for campo in campos}
    for campo in campos:
        setattr(ted, campo, dados[campo])
    ted.save(update_fields=campos)
    log_audit(
        user=usuario, acao="TED.update", modulo="sgp", entidade="TED", entidade_id=ted.pk,
        valores_anteriores=antes, valores_novos={campo: dados[campo] for campo in campos}, request=request,
    )
    return ted
