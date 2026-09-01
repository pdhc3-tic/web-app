import re

import django_filters
from django.db.models import Q

from apps.sgp.models import Activity, FormResponse, UPF


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
            "projeto", "acao", "territorio_id", "tecnico_id",
            "tipo_atividade", "status",
            "data_inicio_after", "data_inicio_before",
        ]


class FormResponseFilter(django_filters.FilterSet):
    formulario_id = django_filters.NumberFilter()
    data_inicio = django_filters.DateFilter(
        field_name="data_preenchimento", lookup_expr="date__gte"
    )
    data_fim = django_filters.DateFilter(
        field_name="data_preenchimento", lookup_expr="date__lte"
    )
    respondente = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = FormResponse
        fields = ["formulario_id", "data_inicio", "data_fim", "respondente"]
