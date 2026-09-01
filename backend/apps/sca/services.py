"""
Serviços do módulo SCA.

Contém:
- registro de dispositivos (device_id → SyncDevice);
- escopo territorial (isolamento por território/carteira);
- motor de resolução de conflito (Estratégias 1–4 da seção 4 do SCA_Requisitos);
- processamento do push (batch, idempotência por uuid_local);
- montagem do pull (delta por since, soft-delete com ativo=false);
- contagem de pendências para o status;
- checagem de expiração de sessão (30 dias) para o refresh SCA.
"""

import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.core.models.notifications import Notification, TipoNotificacao
from apps.core.sensitive_fields import sensitive_fields_visible_to
from apps.core.services.membro_audit import log_membro_change, sensitive_fields_changed
from apps.core.services.permissions import user_territories
from apps.sca.models import ConflictLog, SyncDevice, SyncEvent
from apps.sca.serializers import ENTITY_SERIALIZERS
from apps.sca.sync_entities import SyncEntityError, get_sync_entity

logger = logging.getLogger(__name__)

SESSION_MAX_DAYS = 30
_MISSING = object()


def _jsonable(value):
    """Normaliza valores para serem graváveis em JSONField (conflitos)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


# ---------------------------------------------------------------------------
# Dispositivo
# ---------------------------------------------------------------------------

def get_or_create_device(user, device_id: str, meta: dict | None = None) -> SyncDevice | None:
    if not device_id:
        return None
    meta = meta or {}
    device, _ = SyncDevice.objects.get_or_create(
        user=user,
        device_id=device_id,
        defaults={
            "nome": meta.get("nome", ""),
            "modelo": meta.get("modelo", ""),
            "sistema_operacional": meta.get("sistema_operacional", ""),
            "app_versao": meta.get("app_versao", ""),
        },
    )
    return device


# ---------------------------------------------------------------------------
# Escopo territorial
# ---------------------------------------------------------------------------

def territory_ids_for(user) -> set[int]:
    return set(user_territories(user).values_list("pk", flat=True))


# ---------------------------------------------------------------------------
# Notificações
# ---------------------------------------------------------------------------

def _create_notification(user, *, titulo, mensagem, evento, link="") -> Notification | None:
    if user is None:
        return None
    return Notification.objects.create(
        user=user,
        tipo=TipoNotificacao.IN_APP,
        titulo=titulo,
        mensagem=mensagem,
        evento=evento,
        modulo_origem="sca",
        link=link,
    )


# ---------------------------------------------------------------------------
# Resolução de conflito (Estratégias 2 e 3)
# ---------------------------------------------------------------------------

class MergeResult:
    def __init__(self, changes_to_apply, conflicts, status):
        self.changes_to_apply = changes_to_apply
        self.conflicts = conflicts  # lista de dicts: path, valor_local, valor_servidor, sensitive
        self.status = status  # 'ok' | 'conflito'


def resolve_conflicts(entity, instance, payload_flat, base_flat, incoming_updated_at) -> MergeResult:
    """
    Estratégia 2 — campos diferentes (sem sobreposição): merge automático.
    Estratégia 3 — mesmo campo alterado em ambos: last-write-wins pelo
    updated_at mais recente; ambas as versões vão para conflict_log.
    """
    server_changed: dict = {}
    for path, base_val in base_flat.items():
        server_val = entity.server_field_value(instance, path)
        if entity._norm(base_val) != entity._norm(server_val):
            server_changed[path] = server_val

    local_changed: dict = {}
    for path, val in payload_flat.items():
        base_val = base_flat.get(path, _MISSING)
        if base_val is _MISSING or entity._norm(base_val) != entity._norm(val):
            local_changed[path] = val

    if not local_changed:
        # Idempotência: reenvio com os mesmos valores já no servidor → no-op.
        return MergeResult({}, [], "ok")

    overlaps = set(local_changed) & set(server_changed)

    if not overlaps:
        return MergeResult(dict(local_changed), [], "ok")

    client_wins = incoming_updated_at >= instance.atualizado_em
    to_apply = dict(local_changed)
    conflicts = []
    for path in overlaps:
        is_sensitive = path in entity.sensitive_paths
        conflicts.append(
            {
                "path": path,
                "valor_local": _jsonable(local_changed[path]),
                "valor_servidor": _jsonable(server_changed[path]),
                "sensitive": is_sensitive,
            }
        )
        if is_sensitive:
            if path in to_apply:
                del to_apply[path]
        elif not client_wins:
            if path in to_apply:
                del to_apply[path]

    return MergeResult(to_apply, conflicts, "conflito")


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------

class PushProcessor:
    def __init__(self, user, device, device_id: str = "", tipo_conexao: str | None = None):
        self.user = user
        self.device = device
        self.device_id = device_id or (device.device_id if device else "")
        self.tipo_conexao = tipo_conexao
        self.territory_ids = territory_ids_for(user)
        self.uuid_map: dict[str, int] = {}
        self.visible_sensitive_fields = sensitive_fields_visible_to(user)

    # -- entrada ------------------------------------------------------------
    def process(self, items) -> list[dict]:
        iniciado_em = timezone.now()
        results = []
        for item in items:
            results.append(self._process_item(item))

        if self.device:
            SyncDevice.objects.filter(pk=self.device.pk).update(ultimo_push_em=timezone.now())

        erros_detalhes = []
        for item, r in zip(items, results):
            if r.get("status") == "erro":
                erros_detalhes.append({
                    "uuid_local": str(r.get("uuid_local")),
                    "entidade": item.get("entidade", ""),
                    "mensagem": r.get("erro", ""),
                    "codigo": r.get("erro", "").split(":")[0] if ":" in r.get("erro", "") else "ERRO",
                })

        contagem_erros = len(erros_detalhes)
        finalizado_em = timezone.now()

        SyncEvent.objects.create(
            user=self.user,
            device=self.device,
            tipo=SyncEvent.Tipo.PUSH,
            contagem=len(results),
            contagem_enviados=len(results),
            contagem_recebidos=0,
            contagem_erros=contagem_erros,
            erros_detalhes=erros_detalhes,
            iniciado_em=iniciado_em,
            finalizado_em=finalizado_em,
            tipo_conexao=self.tipo_conexao,
        )
        return results

    def _process_item(self, item) -> dict:
        entity = get_sync_entity(item["entidade"])
        if entity is None:
            return self._result(
                item,
                "erro",
                erro=f"ENTIDADE_NAO_SUPORTADA: entidade '{item['entidade']}' ainda não é suportada no servidor.",
            )
        try:
            # Cada item é atômico: falha de um item não interrompe (nem suja a
            # transação de) itens posteriores do mesmo batch.
            with transaction.atomic():
                return self._dispatch(entity, item)
        except SyncEntityError as exc:
            return self._result(item, "erro", erro=str(exc))
        except (IntegrityError, ValueError) as exc:
            logger.warning("sca.push.item_failed entity=%s uuid=%s error=%s", item["entidade"], item["uuid_local"], exc)
            return self._result(item, "erro", erro="ERRO_INTERNO: falha ao persistir o registro.")

    def _dispatch(self, entity, item) -> dict:
        try:
            data = ENTITY_SERIALIZERS[entity.name](data=item["payload_json"], partial=True)
            data.is_valid(raise_exception=True)
            data = data.validated_data
        except serializers.ValidationError as exc:
            raise SyncEntityError(f"PAYLOAD_INVALIDO: {exc.detail}") from exc
        except KeyError as exc:
            raise SyncEntityError(f"PAYLOAD_INVALIDO: sem serializer para '{entity.name}'.") from exc

        self._reject_unauthorized_sensitive_write(entity, data)

        if item["operacao"] == "create":
            return self._handle_create(entity, item, data)
        return self._handle_update(entity, item, data)

    def _reject_unauthorized_sensitive_write(self, entity, data) -> None:
        negados = [
            path
            for path, sensitive_field in entity.restricted_paths_written(data).items()
            if sensitive_field not in self.visible_sensitive_fields
        ]
        if negados:
            raise SyncEntityError(
                "CAMPO_SENSIVEL_NAO_AUTORIZADO: seu perfil não tem permissão "
                f"para gravar os campos: {', '.join(sorted(negados))}."
            )

    # -- helpers ------------------------------------------------------------
    def _result(self, item, status: str, id_servidor=None, erro=None) -> dict:
        payload = {"uuid_local": str(item["uuid_local"]), "status": status}
        if id_servidor is not None:
            payload["id_servidor"] = id_servidor
        if erro:
            payload["erro"] = erro
        return payload

    def _in_scope_payload(self, entity, data) -> bool:
        t_id = entity.territorio_id_from_payload(data, self.uuid_map)
        return t_id is not None and int(t_id) in self.territory_ids

    def _in_scope_instance(self, entity, instance) -> bool:
        t_id = entity.territorio_of(instance)
        return t_id is not None and int(t_id) in self.territory_ids

    # -- create -------------------------------------------------------------
    def _handle_create(self, entity, item, data) -> dict:
        uuid_local = item["uuid_local"]

        existing = entity.get_by_uuid_local(uuid_local)
        if existing is not None:
            # Idempotência: replay do mesmo create já processado.
            if not self._in_scope_instance(entity, existing):
                return self._result(item, "erro", erro="FORA_TERRITORIO")
            return self._handle_update(entity, item, data, existing=existing)

        if not self._in_scope_payload(entity, data):
            return self._result(item, "erro", erro="FORA_TERRITORIO")

        duplicate = entity.get_by_natural(data)
        if duplicate is not None:
            if not self._in_scope_instance(entity, duplicate):
                return self._result(item, "erro", erro="FORA_TERRITORIO")
            # Estratégia 1 — novo registro vs registro com mesmo identificador natural.
            ConflictLog.objects.create(
                user=self.user,
                device=self.device,
                entidade=entity.name,
                uuid_local=uuid_local,
                campo="__identificador_natural__",
                valor_local=self._norm_payload(entity, data),
                valor_servidor={"id_servidor": duplicate.pk},
                estrategia=ConflictLog.Estrategia.DUPLICATE_REJEITADO,
                campo_sensivel=False,
                status=ConflictLog.Status.RESOLVIDO_AUTO,
                territorio_id=entity.territorio_of(duplicate),
            )
            return self._result(
                item,
                "erro",
                erro=f"DUPLICATA: já existe um registro '{entity.name}' com o mesmo identificador natural.",
            )

        instance = entity.create(
            data,
            user=self.user,
            device_id=self.device_id,
            uuid_local=uuid_local,
            uuid_map=self.uuid_map,
        )
        self.uuid_map[str(uuid_local)] = instance.pk
        self._audit_membro_change(entity, item, "MEMBRO.create", instance, anteriores_sensiveis=None)
        return self._result(item, "ok", id_servidor=instance.pk)

    def _norm_payload(self, entity, data) -> dict:
        return {path: str(value) for path, value in entity.flatten(data).items()}

    # -- auditoria de membro (MembroFamilia via 'member' ou titular via 'upf') --
    def _membro_for_entity(self, entity, instance):
        if entity.name == "member":
            return instance
        if entity.name == "upf":
            return instance.titular
        return None

    def _audit_membro_change(self, entity, item, acao, instance, anteriores_sensiveis) -> None:
        membro = self._membro_for_entity(entity, instance)
        if membro is None:
            return
        novos_sensiveis = {"saude": membro.saude, "cor_raca": membro.cor_raca}
        log_membro_change(
            user=self.user,
            acao=acao,
            membro=membro,
            origem="sca",
            campos_alterados=sensitive_fields_changed(anteriores_sensiveis, novos_sensiveis),
            extra_novos={"device_id": self.device_id, "uuid_local": str(item["uuid_local"])},
        )

    # -- update -------------------------------------------------------------
    def _handle_update(self, entity, item, data, existing=None) -> dict:
        instance = existing or entity.get_by_uuid_local(item["uuid_local"])
        if instance is None:
            instance = entity.get_by_natural(data)

        if instance is None:
            deleted = entity.get_deleted_by_natural(data)
            if deleted is not None:
                return self._strategy4(entity, item, deleted)
            return self._result(item, "erro", erro="NAO_ENCONTRADO: registro não encontrado no servidor.")

        if not self._in_scope_instance(entity, instance):
            return self._result(item, "erro", erro="FORA_TERRITORIO")

        if entity.is_deleted(instance):
            return self._strategy4(entity, item, instance)

        payload_flat = entity.flatten(data)
        base_flat = entity.flatten(item.get("base_json") or {})
        result = resolve_conflicts(
            entity, instance, payload_flat, base_flat, item["updated_at"]
        )

        if result.changes_to_apply:
            membro_antes = self._membro_for_entity(entity, instance)
            anteriores_sensiveis = (
                {"saude": membro_antes.saude, "cor_raca": membro_antes.cor_raca}
                if membro_antes is not None
                else None
            )
            entity.apply_changes(instance, result.changes_to_apply)
            self._audit_membro_change(entity, item, "MEMBRO.update", instance, anteriores_sensiveis)

        self._record_conflicts(entity, item, instance, result)

        if result.status == "conflito":
            return self._result(item, "conflito", id_servidor=instance.pk)
        return self._result(item, "ok", id_servidor=instance.pk)

    def _record_conflicts(self, entity, item, instance, result) -> None:
        territorio_id = entity.territorio_of(instance)
        for conf in result.conflicts:
            is_sensitive = conf["sensitive"]
            status_conflito = (
                ConflictLog.Status.PENDENTE
                if is_sensitive
                else ConflictLog.Status.RESOLVIDO_AUTO
            )
            conflict_log = ConflictLog.objects.create(
                user=self.user,
                device=self.device,
                entidade=entity.name,
                uuid_local=item["uuid_local"],
                campo=conf["path"],
                valor_local=_jsonable(conf["valor_local"]),
                valor_servidor=_jsonable(conf["valor_servidor"]),
                estrategia=ConflictLog.Estrategia.LAST_WRITE_WINS,
                campo_sensivel=is_sensitive,
                status=status_conflito,
                territorio_id=territorio_id,
            )
            if is_sensitive:
                self._notify_articulador(entity, item, instance, conf, conflict_log.pk)

    def _notify_articulador(self, entity, item, instance, conf, conflict_id: int) -> None:
        from apps.core.models import Territory
        from apps.core.models.user_profile import UserProfile

        territorio_id = entity.territorio_of(instance)
        if territorio_id is None:
            logger.warning(
                "sca.notify_articulador sem_territorio entity=%s uuid=%s campo=%s",
                entity.name,
                item["uuid_local"],
                conf["path"],
            )
            return
        try:
            territorio = Territory.objects.get(pk=territorio_id)
        except Territory.DoesNotExist:
            logger.warning(
                "sca.notify_articulador territorio_nao_encontrado territorio_id=%s entity=%s uuid=%s",
                territorio_id,
                entity.name,
                item["uuid_local"],
            )
            return

        if territorio.articulador is not None:
            destinatario_ids = [territorio.articulador_id]
        else:
            # Fallback: sem articulador designado no território, a coordenação
            # (UGP) é notificada para o conflito não passar despercebido.
            logger.warning(
                "sca.notify_articulador sem_articulador territorio_id=%s entity=%s uuid=%s campo=%s — fallback para UGP",
                territorio_id,
                entity.name,
                item["uuid_local"],
                conf["path"],
            )
            destinatario_ids = list(
                UserProfile.objects.filter(
                    perfil__slug="ugp",
                    user__ativo=True,
                    user__acesso_revogado=False,
                )
                .values_list("user_id", flat=True)
                .distinct()
            )
            if not destinatario_ids:
                logger.error(
                    "sca.notify_articulador sem_articulador_e_sem_ugp territorio_id=%s entity=%s uuid=%s",
                    territorio_id,
                    entity.name,
                    item["uuid_local"],
                )
                return

        from apps.sca.tasks import notify_articulador_sync_conflict

        for destinatario_id in destinatario_ids:
            notify_articulador_sync_conflict.delay(
                articulador_id=destinatario_id,
                conflict_id=conflict_id,
                entidade=entity.name,
                uuid_local=str(item["uuid_local"]),
                campo=conf["path"],
                valor_local=conf["valor_local"],
                valor_servidor=conf["valor_servidor"],
                territorio_id=territorio_id,
            )

    def _strategy4(self, entity, item, instance) -> dict:
        """
        Estratégia 4 — registro excluído no servidor mas modificado offline:
        a exclusão prevalece, a modificação local é descartada e o técnico é notificado.
        """
        ConflictLog.objects.create(
            user=self.user,
            device=self.device,
            entidade=entity.name,
            uuid_local=item["uuid_local"],
            campo="__excluido__",
            valor_local=self._norm_payload(entity, item["payload_json"]),
            valor_servidor={"id_servidor": instance.pk, "ativo": False},
            estrategia=ConflictLog.Estrategia.EXCLUSAO_PREVALECE,
            campo_sensivel=False,
            status=ConflictLog.Status.RESOLVIDO_AUTO,
            territorio_id=entity.territorio_of(instance),
        )
        _create_notification(
            self.user,
            titulo="Registro descartado na sincronização",
            mensagem=(
                f"O registro '{entity.name}' que você alterou offline foi excluído no servidor. "
                "A modificação local foi descartada e a exclusão do servidor prevalece."
            ),
            evento="sca.sync.discarded",
        )
        from apps.sca.tasks import notify_tecnico_sync_discard

        notify_tecnico_sync_discard.delay(
            tecnico_id=self.user.pk,
            entidade=entity.name,
            uuid_local=str(item["uuid_local"]),
        )
        return self._result(
            item,
            "erro",
            id_servidor=instance.pk,
            erro="EXCLUIDO_NO_SERVIDOR: o registro foi excluído no servidor e a modificação local foi descartada.",
        )


# ---------------------------------------------------------------------------
# Pull
# ---------------------------------------------------------------------------

def build_pull(user, device, since, tipo_conexao: str | None = None) -> dict:
    from apps.sca.sync_entities import ENTITY_REGISTRY

    iniciado_em = timezone.now()
    territory_ids = territory_ids_for(user)
    server_time = timezone.now()
    payload = {"upfs": [], "members": [], "activities": [], "server_time": server_time.isoformat()}

    if not territory_ids:
        if device:
            SyncDevice.objects.filter(pk=device.pk).update(ultimo_pull_em=server_time)
        SyncEvent.objects.create(
            user=user,
            device=device,
            tipo=SyncEvent.Tipo.PULL,
            since=since,
            contagem=0,
            contagem_enviados=0,
            contagem_recebidos=0,
            contagem_erros=0,
            erros_detalhes=[],
            iniciado_em=iniciado_em,
            finalizado_em=server_time,
            tipo_conexao=tipo_conexao,
        )
        return payload

    visible_sensitive_fields = sensitive_fields_visible_to(user)

    group_key = {"upf": "upfs", "member": "members", "activity": "activities"}
    for entity in ENTITY_REGISTRY.values():
        qs = entity.filter_by_territories(entity.model.objects.all(), territory_ids)
        if since is not None:
            qs = entity.filter_since(qs, since)
        qs = qs.select_related(*_pull_select_related(entity)).prefetch_related(*_pull_prefetch(entity)).order_by("atualizado_em")
        payload[group_key[entity.name]] = [
            entity.redact_restricted(entity.serialize(obj), visible_sensitive_fields)
            for obj in qs
        ]

    if device:
        SyncDevice.objects.filter(pk=device.pk).update(ultimo_pull_em=server_time)
    total = sum(len(v) for v in payload.values() if isinstance(v, list))
    finalizado_em = timezone.now()
    SyncEvent.objects.create(
        user=user,
        device=device,
        tipo=SyncEvent.Tipo.PULL,
        since=since,
        contagem=total,
        contagem_enviados=0,
        contagem_recebidos=total,
        contagem_erros=0,
        erros_detalhes=[],
        iniciado_em=iniciado_em,
        finalizado_em=finalizado_em,
        tipo_conexao=tipo_conexao,
    )
    return payload


def _pull_select_related(entity):
    return {
        "upf": ("titular",),
        "member": ("upf",),
        "activity": ("municipio",),
    }.get(entity.name, ())


def _pull_prefetch(entity):
    return {
        "activity": ("upfs_participantes", "membros_participantes"),
    }.get(entity.name, ())


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def count_pending_records(user, device) -> int:
    from apps.sca.sync_entities import ENTITY_REGISTRY

    territory_ids = territory_ids_for(user)
    if not territory_ids:
        return 0
    since = device.ultimo_pull_em if device else None
    total = 0
    for entity in ENTITY_REGISTRY.values():
        qs = entity.filter_by_territories(entity.model.objects.all(), territory_ids)
        if since is not None:
            qs = entity.filter_since(qs, since)
        total += qs.count()
    return total


def count_pending_records_by_entity(user, device) -> dict[str, int]:
    """Contagem de registros pendentes separados por entidade para o detalhe do dispositivo."""
    from apps.sca.sync_entities import ENTITY_REGISTRY

    territory_ids = territory_ids_for(user)
    if not territory_ids:
        return {name: 0 for name in ENTITY_REGISTRY}

    since = device.ultimo_pull_em if device else None
    result = {}
    for name, entity in ENTITY_REGISTRY.items():
        qs = entity.filter_by_territories(entity.model.objects.all(), territory_ids)
        if since is not None:
            qs = entity.filter_since(qs, since)
        result[name] = qs.count()
    return result


def bulk_count_pending_records(devices, territory_ids_by_user) -> dict[int, int]:
    """Contagem de registros pendentes em lote para a listagem de dispositivos.

    Replica o critério de count_pending_records (escopo territorial do técnico
    + atualizações desde o último pull do dispositivo) com uma consulta por
    entidade: os dispositivos da página entram como agregações condicionais,
    mantendo o custo constante independentemente do tamanho da página.
    """
    from django.db.models import Count, Q

    from apps.sca.sync_entities import ENTITY_REGISTRY

    totals = {device.pk: 0 for device in devices}
    if not devices:
        return totals
    for entity in ENTITY_REGISTRY.values():
        conditional = {}
        for device in devices:
            condition = Q(
                **{
                    f"{entity.territory_lookup}__in": territory_ids_by_user.get(
                        device.user_id
                    )
                    or []
                }
            )
            if device.ultimo_pull_em is not None:
                condition &= Q(atualizado_em__gt=device.ultimo_pull_em)
            conditional[f"dev_{device.pk}"] = Count("pk", filter=condition)
        row = entity.model.objects.aggregate(**conditional)
        for key, value in row.items():
            totals[int(key[4:])] += value or 0
    return totals


# ---------------------------------------------------------------------------
# Refresh SCA
# ---------------------------------------------------------------------------

def last_successful_sync(user, device) -> "object | None":
    if device is not None and device.ultimo_sync_em is not None:
        return device.ultimo_sync_em
    event = (
        SyncEvent.objects.filter(
            user=user,
            tipo__in=[SyncEvent.Tipo.PUSH, SyncEvent.Tipo.PULL],
        )
        .order_by("-finalizado_em")
        .first()
    )
    return event.finalizado_em if event else None


def is_session_expired(user, device) -> bool:
    last = last_successful_sync(user, device)
    if last is None:
        last = user.ultimo_login
        if last is None:
            return False
    return timezone.now() - last > timedelta(days=SESSION_MAX_DAYS)


def register_refresh(user, device) -> None:
    server_time = timezone.now()
    if device:
        SyncDevice.objects.filter(pk=device.pk).update(ultimo_refresh_em=server_time)
    SyncEvent.objects.create(
        user=user,
        device=device,
        tipo=SyncEvent.Tipo.REFRESH,
        contagem=0,
        contagem_enviados=0,
        contagem_recebidos=0,
        contagem_erros=0,
        erros_detalhes=[],
        iniciado_em=server_time,
        finalizado_em=server_time,
    )


# ---------------------------------------------------------------------------
# Forms — fail-safe
# ---------------------------------------------------------------------------

def get_published_forms(since=None, user=None) -> list[dict]:
    """
    Retorna formulários SGF publicados aplicáveis ao sync.

    Quando `user` é informado, o escopo é limitado aos territórios do técnico
    (mesmo isolamento territorial do push/pull): apenas formulários vinculados
    aos territórios do usuário (`territorio` no FormularioSGF) ou formulários
    globais (territorio nulo). Usuários sem territórios vinculados não recebem
    formulários.

    Fail-safe: se o app SGF ainda não estiver disponível (ou o modelo ainda
    não existir), retorna lista vazia sem erro, permitindo que o restante do
    sync funcione normalmente.
    """
    try:
        from apps.sgf.models import FormularioSGF

        territory_ids = territory_ids_for(user) if user is not None else None

        qs = FormularioSGF.objects.filter(status="publicado")
        if since is not None:
            qs = qs.filter(atualizado_em__gt=since)

        if territory_ids is not None:
            if not territory_ids:
                return []
            qs = qs.filter(
                Q(territorio_id__in=territory_ids) | Q(territorio_id__isnull=True)
            )

        return [
            {
                "id": form.pk,
                "nome": form.nome,
                "versao": form.versao,
                "tipo_entidade_alvo": form.tipo_entidade_alvo,
                "schema_json": form.schema_json,
                "atualizado_em": form.atualizado_em.isoformat(),
            }
            for form in qs.order_by("atualizado_em")
        ]
    except Exception:
        return []
