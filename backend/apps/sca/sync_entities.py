"""
Registro de entidades sincronizáveis do SCA (UFPA, membro, atividade).

Cada entidade define:
- como localizar registros por uuid_local / identificador natural (Estratégia 1);
- quais campos são sincronizáveis e como ler/escrever cada um;
- campos sensíveis (nome, CPF, geolocalização) que disparam notificação
  ao Articulador Estadual quando envolvidos em conflito (Estratégia 3);
- como serializar para o pull (mesmo schema do push, para uso como base_json).
"""

from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4

from django.db import models
from django.utils import timezone

from apps.sgp.models import Activity, MembroFamilia, UFPA
from apps.sgp.services.activity_status import (
    ActivityRuleError,
    transition,
    validar_datas,
    validar_membros_participantes,
    validar_transicao,
)
from apps.sgp.services.membro_rules import (
    MembroRuleError,
    normalizar_cpf,
    validar_cpf,
    validar_data_nascimento,
    validar_saude,
    validar_seguridade_social,
    validar_titular_unico,
)


def _resolve_fk_ids(model, data: dict) -> dict:
    """Converte ids inteiros de campos FK em instâncias.

    O payload de sync trafega `*_id` como inteiro; o ORM exige a instância
    para atribuição em ForeignKey.
    """
    resolved = dict(data)
    for field in model._meta.concrete_fields:
        if not isinstance(field, models.ForeignKey):
            continue
        value = resolved.get(field.name)
        if isinstance(value, int):
            obj = field.remote_field.model.objects.filter(pk=value).first()
            if obj is None:
                raise SyncEntityError(f"FK inválida: {field.name}={value} não encontrado.")
            resolved[field.name] = obj
    return resolved


class SyncEntityError(Exception):
    """Erro controlado por item no push — não interrompe o restante do batch."""

    def __init__(self, message, *, sync_code: str = "", campo: str = ""):
        super().__init__(message)
        self.sync_code = sync_code
        self.campo = campo


class SyncEntity:
    name: str = ""
    model = None
    sensitive_paths: tuple = ()
    # Caminho achatado -> nome do campo em SENSITIVE_FIELD_ROLES. Distinto de
    # sensitive_paths (que cobre nome/CPF/geo para fins de conflito): este
    # cobre só os campos com leitura restrita por perfil (saúde, cor/raça).
    restricted_paths: dict = {}
    natural_key_paths: tuple = ()
    id_fields: frozenset = frozenset()
    soft_delete_field: str | None = None
    territory_lookup: str = ""

    # ------------------------------------------------------------------
    # Helpers de valor
    # ------------------------------------------------------------------
    @staticmethod
    def _norm(value):
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        return value

    def _resolve_attr(self, instance, path: str):
        current = instance
        for attr in path.split("."):
            current = getattr(current, attr, None)
            if current is None:
                return None
        return current

    def server_field_value(self, instance, path: str):
        if path in self.id_fields:
            value = self._resolve_attr(instance, f"{path}_id")
        else:
            value = self._resolve_attr(instance, path)
        return self._norm(value)

    def flatten(self, data: dict, prefix: str = ""):
        """Transforma payload aninhado em {caminho.ponto: valor}."""
        out = {}
        for key, value in (data or {}).items():
            if isinstance(value, dict):
                for kk, vv in self.flatten(value, f"{prefix}{key}.").items():
                    out[kk] = vv
            else:
                out[f"{prefix}{key}"] = value
        return out

    def syncable(self, path: str) -> bool:
        return True

    @staticmethod
    def _pop_path(data: dict, path: str) -> None:
        """Remove a chave em `path` (dotted) de um dict aninhado, se existir."""
        parts = path.split(".")
        current = data
        for part in parts[:-1]:
            current = current.get(part) if isinstance(current, dict) else None
            if current is None:
                return
        if isinstance(current, dict):
            current.pop(parts[-1], None)

    def redact_restricted(self, data: dict, visible_fields: set[str]) -> dict:
        """Remove de `data` os campos de `restricted_paths` que `visible_fields` não autoriza."""
        for path, sensitive_field in self.restricted_paths.items():
            if sensitive_field in visible_fields:
                continue
            self._pop_path(data, path)
        return data

    def restricted_paths_written(self, data: dict) -> dict[str, str]:
        """Subconjunto de `restricted_paths` presente em `data` (achatado)."""
        flat = self.flatten(data)
        return {
            path: sensitive_field
            for path, sensitive_field in self.restricted_paths.items()
            if path in flat
        }

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    def base_queryset(self):
        """Queryset usado pelo sync (pull, contagens, lookup por uuid_local).

        Precisa enxergar registros soft-deletados para propagar a exclusão
        aos dispositivos — usa `all_objects` quando o model o expõe (Issue
        #267: UFPA/Activity), com fallback para `objects` nos demais (ex.:
        MembroFamilia, que não tem soft-delete).
        """
        manager = getattr(self.model, "all_objects", self.model.objects)
        return manager.all()

    def get_by_uuid_local(self, uuid):
        if uuid is None:
            return None
        try:
            return self.base_queryset().filter(uuid_local=uuid).first()
        except self.model.DoesNotExist:
            return None

    def get_by_natural(self, data: dict):
        """Busca por identificador natural (ex: CPF). Retorna None se não houver."""
        raise NotImplementedError

    def get_deleted_by_natural(self, data: dict):
        """Registro soft-deletado com o mesmo identificador natural (Estratégia 4)."""
        return None

    # ------------------------------------------------------------------
    # Escopo territorial
    # ------------------------------------------------------------------
    def territorio_id_from_payload(self, data: dict, uuid_map=None) -> int | None:
        raise NotImplementedError

    def territorio_of(self, instance):
        raise NotImplementedError

    def filter_by_territories(self, qs, territory_ids):
        return qs.filter(**{f"{self.territory_lookup}__in": territory_ids})

    def filter_since(self, qs, since):
        return qs.filter(atualizado_em__gt=since)

    def is_deleted(self, instance) -> bool:
        if self.soft_delete_field:
            return not bool(getattr(instance, self.soft_delete_field))
        return False

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------
    def create(self, data: dict, *, user, device_id: str, uuid_local, uuid_map):
        raise NotImplementedError

    def apply_changes(self, instance, changes: dict, *, uuid_map=None):
        """Aplica apenas as mudanças locais aprovadas (merge/Estratégia 2 e 3).

        `uuid_map` resolve referências a entidades criadas no mesmo batch
        (mesmo padrão de `create`) — só `ActivitySyncEntity` usa, para
        `ufpas_participantes`/`membros_participantes`.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Serialização para pull
    # ------------------------------------------------------------------
    def serialize(self, instance) -> dict:
        raise NotImplementedError

    def ensure_uuid_local(self, instance):
        if not instance.uuid_local:
            instance.uuid_local = uuid4()
            instance.save(update_fields=["uuid_local"])
        return instance.uuid_local

    def base_envelope(self, instance, data: dict) -> dict:
        data["id"] = instance.pk
        data["uuid_local"] = str(self.ensure_uuid_local(instance))
        data["atualizado_em"] = timezone.localtime(instance.atualizado_em).isoformat()
        if self.soft_delete_field:
            data["ativo"] = bool(getattr(instance, self.soft_delete_field))
        return data


class UFPASyncEntity(SyncEntity):
    name = "ufpa"
    model = UFPA
    soft_delete_field = "ativo"
    id_fields = frozenset({"projeto", "comunidade", "municipio", "territorio"})
    sensitive_paths = (
        "titular.nome_completo", "titular.cpf", "latitude", "longitude",
        "titular.cor_raca", "titular.saude",
    )
    restricted_paths = {"titular.cor_raca": "cor_raca", "titular.saude": "saude"}
    natural_key_paths = ("titular.cpf",)
    territory_lookup = "territorio_id"

    # ------------------------------------------------------------------
    def territorio_id_from_payload(self, data, uuid_map=None):
        return data.get("territorio")

    def territorio_of(self, instance):
        return instance.territorio_id

    def get_by_natural(self, data):
        titular = data.get("titular") or {}
        cpf = normalizar_cpf(titular.get("cpf"))
        if not cpf:
            return None
        membro = (
            MembroFamilia.objects.filter(cpf=cpf, ufpa__isnull=False)
            .select_related("ufpa")
            .first()
        )
        return membro.ufpa if membro else None

    def get_deleted_by_natural(self, data):
        ufpa = self.get_by_natural(data)
        if ufpa is not None and not ufpa.ativo:
            return ufpa
        return None

    # ------------------------------------------------------------------
    def create(self, data, *, user, device_id, uuid_local, uuid_map):
        titular_data = dict(data.pop("titular", {}) or {})
        if not titular_data.get("nome_completo"):
            raise SyncEntityError("nome_completo do titular é obrigatório para criar UFPA.")

        try:
            titular_data["cpf"] = validar_cpf(titular_data.get("cpf"))
            if "data_nascimento" in titular_data:
                validar_data_nascimento(titular_data["data_nascimento"])
            if "saude" in titular_data:
                validar_saude(titular_data["saude"])
            if "seguridade_social" in titular_data:
                validar_seguridade_social(titular_data["seguridade_social"])
        except MembroRuleError as exc:
            raise SyncEntityError(
                f"{exc.sync_code}: {exc.message}", sync_code=exc.sync_code, campo=exc.field
            ) from exc

        titular = MembroFamilia.objects.create(
            ufpa=None,
            grau_parentesco="titular",
            criado_por=user,
            device_id=device_id,
            uuid_local=None,
            **titular_data,
        )
        try:
            ufpa = UFPA.objects.create(
                titular=titular,
                criado_por=user,
                device_id=device_id,
                uuid_local=uuid_local,
                ultima_origem="sca",
                ultimo_sync_em=timezone.now(),
                **_resolve_fk_ids(UFPA, data),
            )
        except Exception:
            titular.delete()
            raise
        titular.ufpa = ufpa
        titular.ultima_origem = "sca"
        titular.ultimo_sync_em = timezone.now()
        titular.save(update_fields=["ufpa", "ultima_origem", "ultimo_sync_em"])
        return ufpa

    def apply_changes(self, instance, changes: dict, *, uuid_map=None):
        titular_changes = {}
        ufpa_changes = {}
        for path, value in changes.items():
            if path.startswith("titular."):
                titular_changes[path.split(".", 1)[1]] = value
            else:
                ufpa_changes[path] = value

        try:
            if titular_changes.get("cpf"):
                titular_changes["cpf"] = validar_cpf(
                    titular_changes["cpf"], membro_atual=instance.titular
                )
            if "data_nascimento" in titular_changes:
                validar_data_nascimento(titular_changes["data_nascimento"])
            if "saude" in titular_changes:
                validar_saude(titular_changes["saude"])
            if "seguridade_social" in titular_changes:
                validar_seguridade_social(titular_changes["seguridade_social"])
        except MembroRuleError as exc:
            raise SyncEntityError(
                f"{exc.sync_code}: {exc.message}", sync_code=exc.sync_code, campo=exc.field
            ) from exc

        ufpa_changes = _resolve_fk_ids(UFPA, ufpa_changes)
        for field, value in ufpa_changes.items():
            setattr(instance, field, value)
        instance.ultima_origem = "sca"
        instance.ultimo_sync_em = timezone.now()
        instance.save()
        if titular_changes:
            for field, value in titular_changes.items():
                setattr(instance.titular, field, value)
            instance.titular.ultima_origem = "sca"
            instance.titular.ultimo_sync_em = timezone.now()
            instance.titular.save()

    def serialize(self, instance):
        titular = instance.titular
        data = {
            "projeto": instance.projeto_id,
            "comunidade": instance.comunidade_id,
            "municipio": instance.municipio_id,
            "territorio": instance.territorio_id,
            "apelido": instance.apelido,
            "whatsapp": instance.whatsapp,
            "celular": instance.celular,
            "internet": instance.internet,
            "dispositivo": instance.dispositivo,
            "cep": instance.cep,
            "logradouro": instance.logradouro,
            "numero": instance.numero,
            "complemento": instance.complemento,
            "bairro": instance.bairro,
            "latitude": str(instance.latitude) if instance.latitude is not None else None,
            "longitude": str(instance.longitude) if instance.longitude is not None else None,
            "pct": instance.pct,
            "posse_terra": instance.posse_terra,
            "area_terra_ha": str(instance.area_terra_ha) if instance.area_terra_ha is not None else None,
            "situacao_moradia": instance.situacao_moradia,
            "tipo_moradia": instance.tipo_moradia,
            "material_construcao": instance.material_construcao,
            "num_comodos": instance.num_comodos,
            "energia": instance.energia,
            "agua": instance.agua,
            "numero_dap": instance.numero_dap,
            "nis": instance.nis,
            "seguridade_social": list(instance.seguridade_social or []),
            "foto_url": instance.foto_url,
            "ativo": instance.ativo,
            "titular": {
                "nome_completo": titular.nome_completo,
                "cpf": titular.cpf,
                "data_nascimento": titular.data_nascimento.isoformat() if titular.data_nascimento else None,
                "genero": titular.genero,
                "cor_raca": titular.cor_raca,
                "rg": titular.rg,
                "nis": titular.nis,
                "caf": titular.caf,
                "escola": titular.escola,
                "seguridade_social": list(titular.seguridade_social or []),
                "saude": list(titular.saude or []),
                "escolaridade": titular.escolaridade,
            },
        }
        return self.base_envelope(instance, data)


class MemberSyncEntity(SyncEntity):
    name = "member"
    model = MembroFamilia
    id_fields = frozenset({"ufpa"})
    sensitive_paths = ("nome_completo", "cpf", "cor_raca", "saude")
    restricted_paths = {"cor_raca": "cor_raca", "saude": "saude"}
    natural_key_paths = ("cpf",)
    territory_lookup = "ufpa__territorio_id"

    def territorio_id_from_payload(self, data, uuid_map=None):
        ufpa_id = data.get("ufpa")
        if ufpa_id:
            ufpa_obj = UFPA.objects.filter(pk=ufpa_id).only("territorio_id").first()
            return ufpa_obj.territorio_id if ufpa_obj else None
        ufpa_uuid = data.get("ufpa_uuid_local")
        if ufpa_uuid and uuid_map:
            ufpa_id = uuid_map.get(str(ufpa_uuid))
            if ufpa_id:
                ufpa_obj = UFPA.objects.filter(pk=ufpa_id).only("territorio_id").first()
                return ufpa_obj.territorio_id if ufpa_obj else None
        return None

    def territorio_of(self, instance):
        return instance.ufpa.territorio_id if instance.ufpa_id else None

    def get_by_natural(self, data):
        cpf = normalizar_cpf(data.get("cpf"))
        if not cpf:
            return None
        return MembroFamilia.objects.filter(cpf=cpf).exclude(ufpa=None).first()

    def create(self, data, *, user, device_id, uuid_local, uuid_map):
        ufpa_id = data.pop("ufpa", None)
        ufpa_uuid_local = data.pop("ufpa_uuid_local", None)
        if ufpa_uuid_local and ufpa_id is None:
            ufpa_id = uuid_map.get(str(ufpa_uuid_local))
        if ufpa_id is None:
            raise SyncEntityError("Campo 'ufpa' (ou 'ufpa_uuid_local') é obrigatório para criar membro.")
        data["ufpa_id"] = ufpa_id
        try:
            data["cpf"] = validar_cpf(data.get("cpf"))
            if data.get("grau_parentesco") == "titular":
                validar_titular_unico(ufpa_id)
            if "data_nascimento" in data:
                validar_data_nascimento(data["data_nascimento"])
            if "saude" in data:
                validar_saude(data["saude"])
            if "seguridade_social" in data:
                validar_seguridade_social(data["seguridade_social"])
        except MembroRuleError as exc:
            raise SyncEntityError(
                f"{exc.sync_code}: {exc.message}", sync_code=exc.sync_code, campo=exc.field
            ) from exc
        return MembroFamilia.objects.create(
            criado_por=user,
            device_id=device_id,
            uuid_local=uuid_local,
            ultima_origem="sca",
            ultimo_sync_em=timezone.now(),
            **data,
        )

    def apply_changes(self, instance, changes: dict, *, uuid_map=None):
        novo_grau = changes.get("grau_parentesco", instance.grau_parentesco)
        novo_ufpa_id = changes.get("ufpa", instance.ufpa_id)
        try:
            if changes.get("cpf"):
                changes["cpf"] = validar_cpf(changes["cpf"], membro_atual=instance)
            if novo_grau == "titular":
                validar_titular_unico(novo_ufpa_id, membro_atual=instance)
            if "data_nascimento" in changes:
                validar_data_nascimento(changes["data_nascimento"])
            if "saude" in changes:
                validar_saude(changes["saude"])
            if "seguridade_social" in changes:
                validar_seguridade_social(changes["seguridade_social"])
        except MembroRuleError as exc:
            raise SyncEntityError(
                f"{exc.sync_code}: {exc.message}", sync_code=exc.sync_code, campo=exc.field
            ) from exc
        for field, value in changes.items():
            setattr(instance, field, value)
        instance.ultima_origem = "sca"
        instance.ultimo_sync_em = timezone.now()
        instance.save()

    def serialize(self, instance):
        data = {
            "ufpa": instance.ufpa_id,
            "nome_completo": instance.nome_completo,
            "data_nascimento": instance.data_nascimento.isoformat() if instance.data_nascimento else None,
            "genero": instance.genero,
            "cor_raca": instance.cor_raca,
            "cpf": instance.cpf,
            "rg": instance.rg,
            "nis": instance.nis,
            "caf": instance.caf,
            "grau_parentesco": instance.grau_parentesco,
            "escola": instance.escola,
            "seguridade_social": list(instance.seguridade_social or []),
            "saude": list(instance.saude or []),
            "escolaridade": instance.escolaridade,
        }
        return self.base_envelope(instance, data)


class ActivitySyncEntity(SyncEntity):
    name = "activity"
    model = Activity
    soft_delete_field = "ativo"
    id_fields = frozenset({"acao", "municipio", "comunidade", "tecnico_responsavel"})
    sensitive_paths = ("titulo", "latitude", "longitude")
    territory_lookup = "municipio__territory_id"

    def territorio_id_from_payload(self, data, uuid_map=None):
        municipio_id = data.get("municipio")
        if municipio_id:
            from apps.core.models import Municipality

            muni = Municipality.objects.filter(pk=municipio_id).only("territory_id").first()
            return muni.territory_id if muni else None
        return None

    def territorio_of(self, instance):
        return instance.municipio.territory_id if instance.municipio_id else None

    def create(self, data, *, user, device_id, uuid_local, uuid_map):
        ufpas = [self._resolve_participante(item, uuid_map, UFPA) for item in data.pop("ufpas_participantes", [])]
        membros = [self._resolve_participante(item, uuid_map, MembroFamilia) for item in data.pop("membros_participantes", [])]
        novo_status = data.pop("status", None)
        justificativa = data.pop("justificativa", "")

        try:
            validar_datas(data.get("data_inicio"), data.get("data_fim"))
            validar_membros_participantes(ufpas, membros)
        except ActivityRuleError as exc:
            raise SyncEntityError(
                f"{exc.sync_code}: {exc.message}", sync_code=exc.sync_code, campo=exc.field
            ) from exc

        instance = Activity(
            criado_por=user,
            device_id=device_id,
            uuid_local=uuid_local,
            ultima_origem="sca",
            ultimo_sync_em=timezone.now(),
            **_resolve_fk_ids(Activity, data),
        )
        if novo_status is not None:
            try:
                transition(instance, novo_status, usuario=user, justificativa=justificativa)
            except ActivityRuleError as exc:
                raise SyncEntityError(
                    f"{exc.sync_code}: {exc.message}", sync_code=exc.sync_code, campo=exc.field
                ) from exc
        instance.save()
        if ufpas:
            instance.ufpas_participantes.set(ufpas)
        if membros:
            instance.membros_participantes.set(membros)
        return instance

    @staticmethod
    def _resolve_participante(item, uuid_map, model):
        if isinstance(item, str):
            return uuid_map.get(item)
        return item

    def apply_changes(self, instance, changes: dict, *, uuid_map=None):
        changes = _resolve_fk_ids(Activity, changes)

        # Participantes M2M não podem ser atribuídos via setattr (Django
        # recusa com TypeError: "Direct assignment to the forward side of a
        # many-to-many set is prohibited") — tirados de `changes` aqui,
        # resolvidos via uuid_map (igual ao `create`) e gravados com `.set()`
        # depois do save, não pelo loop genérico abaixo.
        ufpas_payload = changes.pop("ufpas_participantes", None)
        membros_payload = changes.pop("membros_participantes", None)

        ufpas_resolvidos = None
        if ufpas_payload is not None:
            ufpas_resolvidos = [
                self._resolve_participante(item, uuid_map, UFPA) for item in ufpas_payload
            ]
            ufpas_ids = set(ufpas_resolvidos)
        else:
            ufpas_ids = set(instance.ufpas_participantes.values_list("pk", flat=True))

        membros_resolvidos = None
        if membros_payload is not None:
            membros_resolvidos = [
                self._resolve_participante(item, uuid_map, MembroFamilia) for item in membros_payload
            ]

        # Resolvidos com fallback pro valor atual da atividade — igual à API
        # web (`ActivityDetailSerializer.validate`): a regra roda em toda
        # atualização, não só quando o campo em questão está no payload.
        novo_status = changes.get("status", instance.status)
        justificativa = changes.get("justificativa", instance.justificativa)
        nova_data = changes.get("data_inicio")
        data_inicio = changes.get("data_inicio", instance.data_inicio)
        data_fim = changes.get("data_fim", instance.data_fim)

        try:
            validar_transicao(
                instance, novo_status, justificativa=justificativa, nova_data=nova_data
            )
            validar_datas(data_inicio, data_fim)
            if membros_resolvidos is not None:
                validar_membros_participantes(ufpas_ids, membros_resolvidos)
        except ActivityRuleError as exc:
            raise SyncEntityError(
                f"{exc.sync_code}: {exc.message}", sync_code=exc.sync_code, campo=exc.field
            ) from exc

        for field, value in changes.items():
            setattr(instance, field, value)
        instance.ultima_origem = "sca"
        instance.ultimo_sync_em = timezone.now()
        instance.save()

        if ufpas_resolvidos is not None:
            instance.ufpas_participantes.set(ufpas_resolvidos)
        if membros_resolvidos is not None:
            instance.membros_participantes.set(membros_resolvidos)

    def serialize(self, instance):
        data = {
            "titulo": instance.titulo,
            "tipo_atividade": instance.tipo_atividade,
            "acao": instance.acao_id,
            "forma_atuacao": instance.forma_atuacao,
            "municipio": instance.municipio_id,
            "comunidade": instance.comunidade_id,
            "tecnico_responsavel": instance.tecnico_responsavel_id,
            "ambito": instance.ambito,
            "latitude": str(instance.latitude) if instance.latitude is not None else None,
            "longitude": str(instance.longitude) if instance.longitude is not None else None,
            "data_inicio": instance.data_inicio.isoformat() if instance.data_inicio else None,
            "data_fim": instance.data_fim.isoformat() if instance.data_fim else None,
            "parceiros_livres": instance.parceiros_livres,
            "descricao_narrativa": instance.descricao_narrativa,
            "resultados_alcancados": instance.resultados_alcancados,
            "status": instance.status,
            "justificativa": instance.justificativa,
            "ufpas_participantes": [ufpa.pk for ufpa in instance.ufpas_participantes.all()],
            "membros_participantes": [membro.pk for membro in instance.membros_participantes.all()],
            "ativo": instance.ativo,
        }
        return self.base_envelope(instance, data)


ENTITY_REGISTRY: dict[str, SyncEntity] = {
    "ufpa": UFPASyncEntity(),
    "member": MemberSyncEntity(),
    "activity": ActivitySyncEntity(),
}


def espelho_de_saldo(user) -> list[dict]:
    """Os cartões de "meu saldo" no momento do sync, em formato que vai direto para o JSON."""
    from apps.sgp.budget.meu_saldo import saldo_por_rubrica
    from apps.sgp.budget.serializers import MeuSaldoSerializer

    return [dict(linha) for linha in MeuSaldoSerializer(saldo_por_rubrica(user), many=True).data]


def get_sync_entity(name: str) -> SyncEntity | None:
    return ENTITY_REGISTRY.get(name)
