from apps.sgp.services.form_response_render import (
    EMPTY_RESPONSE_MESSAGE,
    build_response_tree,
    humanize_label,
    stringify_primitive,
)


def test_humanize_label_snake_case_and_hyphenated_keys():
    assert humanize_label("renda_familiar") == "Renda familiar"
    assert humanize_label("atividade-principal") == "Atividade principal"


def test_humanize_label_leaves_already_spaced_keys_untouched():
    assert humanize_label("Renda Familiar Mensal") == "Renda Familiar Mensal"


def test_build_tree_preserves_dict_iteration_order():
    respostas = {"c": 1, "a": 2, "b": 3}
    tree = build_response_tree(respostas)
    assert [node.label for node in tree] == ["C", "A", "B"]


def test_build_tree_renders_none_as_em_dash():
    tree = build_response_tree({"observacoes": None})
    assert tree[0].kind == "primitive"
    assert tree[0].text == "—"


def test_build_tree_renders_bool_as_sim_nao():
    tree = build_response_tree({"possui_energia": True, "possui_agua": False})
    assert tree[0].text == "Sim"
    assert tree[1].text == "Não"


def test_build_tree_renders_empty_list_and_empty_dict_as_em_dash():
    tree = build_response_tree({"culturas": [], "endereco": {}})
    assert tree[0].kind == "primitive"
    assert tree[0].text == "—"
    assert tree[1].kind == "primitive"
    assert tree[1].text == "—"


def test_build_tree_renders_primitive_list_as_chips_node():
    tree = build_response_tree({"culturas": ["Milho", "Feijão", "Mandioca"]})
    assert tree[0].kind == "chips"
    assert tree[0].chips == ("Milho", "Feijão", "Mandioca")


def test_build_tree_renders_mixed_list_with_null_and_primitives_as_chips():
    tree = build_response_tree({"respostas": ["Sim", None, "Não"]})
    assert tree[0].kind == "chips"
    assert tree[0].chips == ("Sim", "—", "Não")


def test_build_tree_renders_list_of_dicts_as_numbered_group_items():
    tree = build_response_tree(
        {"membros_familia": [{"nome": "Ana"}, {"nome": "Beto"}]}
    )
    node = tree[0]
    assert node.kind == "group"
    assert [child.label for child in node.children] == ["Item 1", "Item 2"]
    assert node.children[0].kind == "group"
    assert node.children[0].children[0].label == "Nome"
    assert node.children[0].children[0].text == "Ana"


def test_build_tree_renders_nested_dict_as_group():
    tree = build_response_tree({"endereco": {"municipio": "Mossoró", "estado": "RN"}})
    node = tree[0]
    assert node.kind == "group"
    assert [child.label for child in node.children] == ["Municipio", "Estado"]
    assert node.children[0].text == "Mossoró"


def test_build_tree_does_not_reformat_numbers_dates_or_currency_strings():
    respostas = {
        "data_visita": "2026-01-05",
        "renda": "R$ 1.234,56",
        "idade": 42,
        "peso": 3.5,
    }
    tree = build_response_tree(respostas)
    values = {node.label: node.text for node in tree}
    assert values["Data visita"] == "2026-01-05"
    assert values["Renda"] == "R$ 1.234,56"
    assert values["Idade"] == "42"
    assert values["Peso"] == "3.5"


def test_build_tree_empty_or_none_respostas_json_returns_empty_list():
    assert build_response_tree(None) == []
    assert build_response_tree({}) == []


def test_stringify_primitive_matches_frontend_rules():
    assert stringify_primitive(None) == "—"
    assert stringify_primitive(True) == "Sim"
    assert stringify_primitive(False) == "Não"
    assert stringify_primitive("Agricultura") == "Agricultura"
    assert stringify_primitive(7) == "7"


def test_empty_response_message_matches_frontend_copy():
    assert EMPTY_RESPONSE_MESSAGE == (
        "Este formulário foi submetido sem respostas registradas."
    )
