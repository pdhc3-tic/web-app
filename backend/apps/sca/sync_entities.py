"""
Registro de entidades sincronizáveis do SCA (UPF, membro, atividade).

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

from apps.sgp.models import Activity, MembroFamilia, UPF


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


class SyncEntity:
    name: str = ""
    model = None
    sensitive_paths: tuple = ()
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

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    def get_by_uuid_local(self, uuid):
        if uuid is None:
            return None
        try:
            return self.model.objects.filter(uuid_local=uuid).first()
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

    def apply_changes(self, instance, changes: dict):
        """Aplica apenas as mudanças locais aprovadas (merge/Estratégia 2 e 3)."""
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


class UPFSyncEntity(SyncEntity):
    name = "upf"
    model = UPF
    soft_delete_field = "ativa"
    id_fields = frozenset({"projeto", "comunidade", "municipio", "territorio"})
    sensitive_paths = ("titular.nome_completo", "titular.cpf", "latitude", "longitude")
    natural_key_paths = ("titular.cpf",)
    territory_lookup = "territorio_id"

    # ------------------------------------------------------------------
    def territorio_id_from_payload(self, data, uuid_map=None):
        return data.get("territorio")

    def territorio_of(self, instance):
        return instance.territorio_id

    def get_by_natural(self, data):
        titular = data.get("titular") or {}
        cpf = (titular.get("cpf") or "").strip()
        if not cpf:
            return None
        membro = (
            MembroFamilia.objects.filter(cpf=cpf, upf__isnull=False)
            .select_related("upf")
            .first()
        )
        return membro.upf if membro else None

    def get_deleted_by_natural(self, data):
        upf = self.get_by_natural(data)
        if upf is not None and not upf.ativa:
            return upf
        return None

    # ------------------------------------------------------------------
    def create(self, data, *, user, device_id, uuid_local, uuid_map):
        titular_data = dict(data.pop("titular", {}) or {})
        if not titular_data.get("nome_completo"):
            raise SyncEntityError("nome_completo do titular é obrigatório para criar UPF.")

        titular = MembroFamilia.objects.create(
            upf=None,
            parentesco="titular",
            criado_por=user,
            device_id=device_id,
            uuid_local=None,
            **titular_data,
        )
        try:
            upf = UPF.objects.create(
                titular=titular,
                criado_por=user,
                device_id=device_id,
                uuid_local=uuid_local,
                ultima_origem="sca",
                ultimo_sync_em=timezone.now(),
                **_resolve_fk_ids(UPF, data),
            )
        except Exception:
            titular.delete()
            raise
        titular.upf = upf
        titular.ultima_origem = "sca"
        titular.ultimo_sync_em = timezone.now()
        titular.save(update_fields=["upf", "ultima_origem", "ultimo_sync_em"])
        return upf

    def apply_changes(self, instance, changes: dict):
        titular_changes = {}
        upf_changes = {}
        for path, value in changes.items():
            if path.startswith("titular."):
                titular_changes[path.split(".", 1)[1]] = value
            else:
                upf_changes[path] = value
        upf_changes = _resolve_fk_ids(UPF, upf_changes)
        for field, value in upf_changes.items():
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
            "ativa": instance.ativa,
            "titular": {
                "nome_completo": titular.nome_completo,
                "cpf": titular.cpf,
                "data_nasc": titular.data_nasc.isoformat() if titular.data_nasc else None,
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
    id_fields = frozenset({"upf"})
    sensitive_paths = ("nome_completo", "cpf")
    natural_key_paths = ("cpf",)
    territory_lookup = "upf__territorio_id"

    def territorio_id_from_payload(self, data, uuid_map=None):
        upf_id = data.get("upf")
        if upf_id:
            upf_obj = UPF.objects.filter(pk=upf_id).only("territorio_id").first()
            return upf_obj.territorio_id if upf_obj else None
        upf_uuid = data.get("upf_uuid_local")
        if upf_uuid and uuid_map:
            upf_id = uuid_map.get(str(upf_uuid))
            if upf_id:
                upf_obj = UPF.objects.filter(pk=upf_id).only("territorio_id").first()
                return upf_obj.territorio_id if upf_obj else None
        return None

    def territorio_of(self, instance):
        return instance.upf.territorio_id if instance.upf_id else None

    def get_by_natural(self, data):
        cpf = (data.get("cpf") or "").strip()
        if not cpf:
            return None
        return MembroFamilia.objects.filter(cpf=cpf).exclude(upf=None).first()

    def create(self, data, *, user, device_id, uuid_local, uuid_map):
        upf_id = data.pop("upf", None)
        upf_uuid_local = data.pop("upf_uuid_local", None)
        if upf_uuid_local and upf_id is None:
            upf_id = uuid_map.get(str(upf_uuid_local))
        if upf_id is None:
            raise SyncEntityError("Campo 'upf' (ou 'upf_uuid_local') é obrigatório para criar membro.")
        data["upf_id"] = upf_id
        return MembroFamilia.objects.create(
            criado_por=user,
            device_id=device_id,
            uuid_local=uuid_local,
            ultima_origem="sca",
            ultimo_sync_em=timezone.now(),
            **data,
        )

    def apply_changes(self, instance, changes: dict):
        for field, value in changes.items():
            setattr(instance, field, value)
        instance.ultima_origem = "sca"
        instance.ultimo_sync_em = timezone.now()
        instance.save()

    def serialize(self, instance):
        data = {
            "upf": instance.upf_id,
            "nome_completo": instance.nome_completo,
            "data_nasc": instance.data_nasc.isoformat() if instance.data_nasc else None,
            "genero": instance.genero,
            "cor_raca": instance.cor_raca,
            "cpf": instance.cpf,
            "rg": instance.rg,
            "nis": instance.nis,
            "caf": instance.caf,
            "parentesco": instance.parentesco,
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
        upfs = [self._resolve_participante(item, uuid_map, UPF) for item in data.pop("upfs_participantes", [])]
        membros = [self._resolve_participante(item, uuid_map, MembroFamilia) for item in data.pop("membros_participantes", [])]
        instance = Activity.objects.create(
            criado_por=user,
            device_id=device_id,
            uuid_local=uuid_local,
            ultima_origem="sca",
            ultimo_sync_em=timezone.now(),
            **_resolve_fk_ids(Activity, data),
        )
        if upfs:
            instance.upfs_participantes.set(upfs)
        if membros:
            instance.membros_participantes.set(membros)
        return instance

    @staticmethod
    def _resolve_participante(item, uuid_map, model):
        if isinstance(item, str):
            return uuid_map.get(item)
        return item

    def apply_changes(self, instance, changes: dict):
        changes = _resolve_fk_ids(Activity, changes)
        for field, value in changes.items():
            setattr(instance, field, value)
        instance.ultima_origem = "sca"
        instance.ultimo_sync_em = timezone.now()
        instance.save()

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
            "parceiros": instance.parceiros,
            "descricao_narrativa": instance.descricao_narrativa,
            "resultados_alcancados": instance.resultados_alcancados,
            "status": instance.status,
            "justificativa": instance.justificativa,
            "upfs_participantes": [upf.pk for upf in instance.upfs_participantes.all()],
            "membros_participantes": [membro.pk for membro in instance.membros_participantes.all()],
            "ativo": instance.ativo,
        }
        return self.base_envelope(instance, data)


ENTITY_REGISTRY: dict[str, SyncEntity] = {
    "upf": UPFSyncEntity(),
    "member": MemberSyncEntity(),
    "activity": ActivitySyncEntity(),
}


def get_sync_entity(name: str) -> SyncEntity | None:
    return ENTITY_REGISTRY.get(name)
