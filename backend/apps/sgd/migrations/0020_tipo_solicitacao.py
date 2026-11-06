import django.db.models.deletion
from django.db import migrations, models

# Copiado de propósito: migrations não importam código de app que pode mudar.
_INTEIRO_POSITIVO = {
    "type": ["integer", "string"],
    "pattern": r"^\s*\+?0*[1-9][0-9]*\s*$",
    "minimum": 1,
    "mensagem": "Deve ser um número inteiro maior que zero.",
}
_URGENCIA = ["normal", "urgente", "emergencial"]
# None e "" já saem em validar_por_schema.
_NAO_PREENCHIDO = [False, 0, [], {}]


def _campo(titulo, **regras):
    return {"title": titulo, **regras}


def _obrigatorio_se(campo, mensagem):
    return {
        "required": [campo],
        "properties": {campo: {"not": {"enum": _NAO_PREENCHIDO}, "mensagem": mensagem}},
        "mensagem": mensagem,
    }


_DIARIA = {
    "type": "object",
    "required": [
        "beneficiario_nome", "beneficiario_cpf", "beneficiario_cargo", "beneficiario_vinculo",
        "municipio_destino_id", "data_inicio", "data_fim", "meio_transporte", "justificativa",
    ],
    "properties": {
        "beneficiario_nome": _campo("Beneficiário: nome completo"),
        "beneficiario_cpf": _campo("Beneficiário: CPF"),
        "beneficiario_cargo": _campo("Beneficiário: cargo ou função"),
        "beneficiario_vinculo": _campo(
            "Beneficiário: vínculo", enum=["servidor_ufersa", "bolsista", "colaborador_externo"],
        ),
        "municipio_destino_id": _campo("Município de destino"),
        "data_inicio": _campo("Data de início"),
        "data_fim": _campo("Data de fim"),
        "meio_transporte": _campo("Meio de transporte", enum=["aereo", "rodoviario", "proprio", "outro"]),
        "justificativa": _campo("Justificativa"),
    },
}
_PASSAGEM = {
    "type": "object",
    "required": [
        "passageiro_nome", "passageiro_cpf", "passageiro_data_nascimento", "aeroporto_origem", "aeroporto_destino",
        "data_hora_ida", "ida_e_volta", "bagagem_despachada", "classe", "urgencia",
    ],
    "properties": {
        "passageiro_nome": _campo("Passageiro: nome completo"),
        "passageiro_cpf": _campo("Passageiro: CPF"),
        "passageiro_data_nascimento": _campo("Passageiro: data de nascimento"),
        "aeroporto_origem": _campo("Aeroporto de origem"),
        "aeroporto_destino": _campo("Aeroporto de destino"),
        "data_hora_ida": _campo("Data e hora do voo de ida"),
        "ida_e_volta": _campo("Viagem de ida e volta?", type="boolean", mensagem="Deve ser um booleano."),
        "data_hora_volta": _campo("Data e hora do voo de volta"),
        "bagagem_despachada": _campo("Bagagem despachada"),
        "classe": _campo("Classe", enum=["economica", "executiva"]),
        "justificativa_executiva": _campo("Justificativa para executiva"),
        "urgencia": _campo("Urgência", enum=_URGENCIA),
    },
    "allOf": [
        {
            "if": {"required": ["ida_e_volta"], "properties": {"ida_e_volta": {"const": True}}},
            "then": _obrigatorio_se("data_hora_volta", "Obrigatório quando 'Viagem de ida e volta' é verdadeiro."),
        },
        {
            "if": {"required": ["classe"], "properties": {"classe": {"const": "executiva"}}},
            "then": _obrigatorio_se("justificativa_executiva", "Obrigatório quando a classe é Executiva."),
        },
    ],
}
_VEICULO = {
    "type": "object",
    "required": [
        "tipo_veiculo", "data_hora_retirada", "data_hora_devolucao", "destino_rota", "estimativa_km",
        "motorista_incluso", "combustivel_incluso", "numero_passageiros",
    ],
    "properties": {
        "tipo_veiculo": _campo("Tipo de veículo", enum=["hatch", "sedan", "suv", "van", "micro_onibus", "onibus"]),
        "data_hora_retirada": _campo("Data e hora de retirada"),
        "data_hora_devolucao": _campo("Data e hora de devolução"),
        "destino_rota": _campo("Destino ou rota"),
        "estimativa_km": _campo("Estimativa de quilometragem", **_INTEIRO_POSITIVO),
        "motorista_incluso": _campo("Motorista incluso?"),
        "combustivel_incluso": _campo("Combustível incluso?"),
        "numero_passageiros": _campo("Número de passageiros", **_INTEIRO_POSITIVO),
        "finalidade": _campo("Finalidade"),
    },
}
_GRAFICO = {
    "type": "object",
    "required": ["tipo_material", "quantidade", "especificacoes_tecnicas", "prazo_entrega"],
    "properties": {
        "tipo_material": _campo(
            "Tipo de material",
            enum=["banner", "folder", "camiseta", "bloco", "caneta", "chapeu", "kit_evento", "outro"],
        ),
        "quantidade": _campo("Quantidade", **_INTEIRO_POSITIVO),
        "especificacoes_tecnicas": _campo("Especificações técnicas"),
        "prazo_entrega": _campo(
            "Prazo de entrega necessário", type="string", format="date", mensagem="Data inválida.",
        ),
        "fornecedor_sugerido": _campo("Fornecedor sugerido"),
        "finalidade_evento": _campo("Finalidade ou evento"),
    },
}
_ALIMENTACAO = {
    "type": "object",
    "required": ["tipo_refeicao", "data_horario_servico", "numero_pessoas"],
    "properties": {
        "tipo_refeicao": _campo(
            "Tipo de refeição", enum=["cafe_manha", "almoco", "jantar", "coffee_break", "kit_lanche", "marmitex"],
        ),
        "data_horario_servico": _campo("Data e horário do serviço"),
        "numero_pessoas": _campo("Número de pessoas", **_INTEIRO_POSITIVO),
        "local_entrega": _campo("Local de entrega ou endereço"),
        "restricoes_alimentares": _campo("Restrições alimentares"),
    },
}
_EQUIPAMENTO = {
    "type": "object",
    "required": [
        "descricao_equipamento", "especificacao_tecnica_detalhada", "quantidade", "finalidade_justificativa",
        "urgencia",
    ],
    "properties": {
        "descricao_equipamento": _campo("Descrição do equipamento"),
        "especificacao_tecnica_detalhada": _campo("Especificação técnica detalhada"),
        "quantidade": _campo("Quantidade", **_INTEIRO_POSITIVO),
        "finalidade_justificativa": _campo("Finalidade e justificativa"),
        "fornecedor_preferencial": _campo("Fornecedor preferencial"),
        "urgencia": _campo("Urgência", enum=_URGENCIA),
    },
}

# slug, nome, slug da rubrica padrão, schema_campos.
TIPOS = [
    ("diaria", "Diárias", "diarias", _DIARIA),
    ("passagem", "Passagens Aéreas", "passagens-aereas", _PASSAGEM),
    ("veiculo", "Locação de Veículo", "locacao-veiculo", _VEICULO),
    ("grafico", "Material Gráfico", "material-grafico", _GRAFICO),
    ("alimentacao", "Alimentação", "alimentacao-refeicoes", _ALIMENTACAO),
    ("equipamento", "Aquisição de Equipamentos", "equipamentos-capital", _EQUIPAMENTO),
]


def semear_catalogo(apps, schema_editor):
    """A rubrica vem do mapeamento ativo. Sem ele o tipo já não aceitava solicitação nova:
    nasce inativo, com a rubrica padrão."""
    Tipo = apps.get_model("sgd", "TipoSolicitacao")
    Rubrica = apps.get_model("sgp", "BudgetRubrica")
    Mapeamento = apps.get_model("sgd", "DemandTypeRubricaMapping")
    for ordem, (slug, nome, rubrica_padrao, schema) in enumerate(TIPOS, start=1):
        mapeamento = Mapeamento.objects.filter(tipo=slug, ativo=True).first()
        rubrica_id = mapeamento.rubrica_id if mapeamento else Rubrica.objects.get_or_create(
            slug=rubrica_padrao, defaults={"nome": nome},
        )[0].pk
        Tipo.objects.create(
            slug=slug, nome=nome, rubrica_id=rubrica_id, schema_campos=schema, validador=slug,
            ativo=mapeamento is not None, ordem=ordem,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("sgd", "0019_remover_demandindividuallimit"),
        ("sgp", "0017_ajustes_de_pool_e_limite"),
    ]

    operations = [
        migrations.CreateModel(
            name="TipoSolicitacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(unique=True, verbose_name="Identificador")),
                ("nome", models.CharField(max_length=100, verbose_name="Nome")),
                ("schema_campos", models.JSONField(
                    blank=True, default=dict, verbose_name="Campos do formulário (JSON Schema)",
                )),
                ("validador", models.CharField(blank=True, default="", max_length=50, verbose_name="Validador")),
                ("ativo", models.BooleanField(default=True, verbose_name="Ativo")),
                ("ordem", models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("rubrica", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="tipos_solicitacao_sgd",
                    to="sgp.budgetrubrica", verbose_name="Rubrica",
                )),
            ],
            options={
                "verbose_name": "Tipo de solicitação",
                "verbose_name_plural": "Tipos de solicitação",
                "ordering": ["ordem", "nome"],
            },
        ),
        migrations.RunPython(semear_catalogo, migrations.RunPython.noop),
    ]
