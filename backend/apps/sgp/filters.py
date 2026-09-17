import re

import django_filters
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.sgp.models import Activity, FormResponse, Tecnico, UPF


class StrictBooleanWidget(forms.Select):
    """Como o `BooleanWidget` do django-filter, mas não converte valores não
    reconhecidos em `None` — isso é necessário para que `StrictBooleanField`
    consiga distinguir "não informado" de "informado incorretamente" e
    rejeitar o segundo caso com 400."""

    def __init__(self, attrs=None):
        choices = (("", "Unknown"), ("true", "Yes"), ("false", "No"))
        super().__init__(attrs, choices)

    def value_from_datadict(self, data, files, name):
        return data.get(name)


class StrictBooleanField(forms.NullBooleanField):
    """Como `NullBooleanField`, mas rejeita valores não reconhecidos em vez
    de tratá-los como "não informado". O `NullBooleanField` padrão (usado
    pelo `django_filters.BooleanFilter`) faz `to_python` retornar `None`
    para qualquer string não reconhecida, então um parâmetro inválido é
    silenciosamente ignorado ao invés de rejeitado com 400."""

    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().lower()
        if value in (None, ""):
            return None
        if value in (True, "true", "1"):
            return True
        if value in (False, "false", "0"):
            return False
        raise ValidationError(
            "Informe um valor booleano (true ou false).", code="invalid"
        )


class StrictBooleanFilter(django_filters.BooleanFilter):
    field_class = StrictBooleanField


class UPFFilter(django_filters.FilterSet):
    municipio = django_filters.NumberFilter(field_name="municipio_id")
    territorio = django_filters.NumberFilter(field_name="territorio_id")
    projeto = django_filters.NumberFilter(field_name="projeto_id")
    comunidade = django_filters.NumberFilter(field_name="comunidade_id")
    ativa = django_filters.BooleanFilter()
    cadastrado_de = django_filters.DateFilter(
        field_name="criado_em", lookup_expr="date__gte"
    )
    cadastrado_ate = django_filters.DateFilter(
        field_name="criado_em", lookup_expr="date__lte"
    )
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = UPF
        fields = [
            "municipio",
            "territorio",
            "projeto",
            "comunidade",
            "ativa",
            "cadastrado_de",
            "cadastrado_ate",
            "q",
        ]

    def filter_q(self, queryset, name, value):
        q = Q(titular__nome_completo__icontains=value)
        digits_only = re.sub(r"\D", "", value)
        if digits_only:
            q |= Q(titular__cpf__startswith=digits_only)
        return queryset.filter(q)


class ActivityFilter(django_filters.FilterSet):
    projeto = django_filters.NumberFilter(field_name="acao__meta__projeto_id", label="Projeto")
    acao = django_filters.NumberFilter(field_name="acao_id", label="Ação")
    territorio_id = django_filters.NumberFilter(
        field_name="municipio__territory_id", label="Território"
    )
    tecnico_id = django_filters.NumberFilter(
        field_name="tecnico_responsavel_id", label="Técnico Responsável"
    )
    osc = django_filters.NumberFilter(
        field_name="tecnico_responsavel__tecnico__osc_id",
        label="OSC do Técnico Responsável",
    )
    parceiro = django_filters.NumberFilter(
        field_name="parceiros_organizacoes", label="Parceiro (Organização)"
    )
    tipo_atividade = django_filters.ChoiceFilter(
        choices=[
            ("visita_tecnica", "Visita técnica"),
            ("reuniao_comunitaria", "Reunião comunitária"),
            ("oficina", "Oficina"),
            ("intercambio", "Intercâmbio"),
            ("curso_capacitacao", "Curso/Capacitação"),
            ("dia_de_campo", "Dia de campo"),
            ("seminario", "Seminário"),
            ("encontro", "Encontro"),
            ("dia_de_partilha", "Dia de partilha"),
            ("atividade_interna", "Atividade interna"),
            ("pesquisa_de_campo", "Pesquisa de campo"),
            ("ater", "Assistência técnica/ATER"),
            ("outro", "Outro"),
        ],
        label="Tipo de Atividade",
    )
    status = django_filters.ChoiceFilter(
        choices=[
            ("planejado", "Planejado"),
            ("agendado", "Agendado"),
            ("em_andamento", "Em andamento"),
            ("concluido", "Concluído"),
            ("concluido_sem_evidencia", "Concluído sem evidência"),
            ("adiada", "Adiada"),
            ("nao_realizada", "Não realizada"),
            ("cancelada", "Cancelada"),
        ],
        label="Status",
    )
    data_inicio_after = django_filters.DateFilter(
        field_name="data_inicio", lookup_expr="gte", label="Data Início (após)"
    )
    data_inicio_before = django_filters.DateFilter(
        field_name="data_inicio", lookup_expr="lte", label="Data Início (antes)"
    )

    class Meta:
        model = Activity
        fields = [
            "projeto", "acao", "territorio_id", "tecnico_id", "osc", "parceiro",
            "tipo_atividade", "status",
            "data_inicio_after", "data_inicio_before",
        ]


class TecnicoFilter(django_filters.FilterSet):
    osc = django_filters.NumberFilter(field_name="osc_id", label="OSC")
    territorio = django_filters.NumberFilter(field_name="territorio_id", label="Território")
    ativo = django_filters.BooleanFilter()
    papel = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Tecnico
        fields = ["osc", "territorio", "ativo", "papel"]


class FormResponseFilter(django_filters.FilterSet):
    formulario_id = django_filters.NumberFilter()
    data_inicio = django_filters.DateFilter(
        field_name="data_preenchimento", lookup_expr="date__gte"
    )
    data_fim = django_filters.DateFilter(
        field_name="data_preenchimento", lookup_expr="date__lte"
    )
    respondente = django_filters.CharFilter(lookup_expr="icontains")
    # `true` retorna somente respostas anônimas (respondente IS NULL); `false`
    # inverte a condição. Valor não booleano é rejeitado com 400 pelo
    # DjangoFilterBackend (raise_exception=True por padrão) — o
    # StrictBooleanFilter garante que o erro realmente seja levantado, ao
    # invés do parâmetro inválido ser ignorado silenciosamente.
    respondente_isnull = StrictBooleanFilter(
        field_name="respondente",
        lookup_expr="isnull",
        widget=StrictBooleanWidget,
    )

    class Meta:
        model = FormResponse
        fields = [
            "formulario_id",
            "data_inicio",
            "data_fim",
            "respondente",
            "respondente_isnull",
        ]
