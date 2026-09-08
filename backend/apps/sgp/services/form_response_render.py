"""Renderização canônica de FormResponse.respostas_json — Issue #205.

Espelha as regras de exibição do modal de visualização completa
(FE-17/BE-17, frontend RespostaFormularioSlideOver.tsx): como o SGP não
persiste hoje um schema/definição versionada dos formulários do SGF, tanto
o modal quanto este módulo tratam respostas_json de forma "schema-less" —
humanizam a chave em vez de resolver o rótulo real da pergunta/opção, e
despacham por tipo de valor (None, bool, list, dict, primitivo).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

EMPTY_RESPONSE_MESSAGE = "Este formulário foi submetido sem respostas registradas."

NodeKind = Literal["primitive", "chips", "group"]

_PRIMITIVE_TYPES = (str, int, float, bool)


@dataclass(frozen=True)
class FieldNode:
    label: str
    kind: NodeKind
    text: str | None = None
    chips: tuple[str, ...] = ()
    children: tuple["FieldNode", ...] = field(default_factory=tuple)


def humanize_label(key: str) -> str:
    """"renda_familiar" -> "Renda familiar". Chaves já humanizadas ficam intactas."""
    if any(ch.isspace() for ch in key):
        return key
    sem_sep = key.replace("_", " ").replace("-", " ").strip()
    if not sem_sep:
        return sem_sep
    return sem_sep[0].upper() + sem_sep[1:]


def stringify_primitive(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    return str(value)


def _is_primitive(value: object) -> bool:
    return value is None or isinstance(value, _PRIMITIVE_TYPES)


def _build_field(key: str, value: object, level: int) -> FieldNode:
    label = humanize_label(key)

    if value is None:
        return FieldNode(label=label, kind="primitive", text="—")

    if isinstance(value, list):
        if len(value) == 0:
            return FieldNode(label=label, kind="primitive", text="—")
        if all(_is_primitive(item) for item in value):
            chips = tuple(stringify_primitive(item) for item in value)
            return FieldNode(label=label, kind="chips", chips=chips)
        children = tuple(
            _build_field(f"Item {idx + 1}", item, level + 1)
            for idx, item in enumerate(value)
        )
        return FieldNode(label=label, kind="group", children=children)

    if isinstance(value, dict):
        if len(value) == 0:
            return FieldNode(label=label, kind="primitive", text="—")
        children = tuple(
            _build_field(child_key, child_value, level + 1)
            for child_key, child_value in value.items()
        )
        return FieldNode(label=label, kind="group", children=children)

    return FieldNode(label=label, kind="primitive", text=stringify_primitive(value))


def build_response_tree(respostas_json: dict | None) -> list[FieldNode]:
    if not respostas_json:
        return []
    return [_build_field(key, value, 0) for key, value in respostas_json.items()]


# --- Construção de flowables reportlab (import tardio, mesma convenção já
#     usada em FormResponseViewSet._pdf_response). ---

INDENT_STEP_CM = 0.5


def build_field_styles(styles) -> dict:
    from reportlab.lib.styles import ParagraphStyle

    return {
        "field": ParagraphStyle(
            "FormResponseField", parent=styles["BodyText"], leading=14, spaceAfter=2
        ),
        "group_title": ParagraphStyle(
            "FormResponseGroupTitle",
            parent=styles["Heading4"],
            spaceBefore=8,
            spaceAfter=4,
        ),
        "empty": ParagraphStyle(
            "FormResponseEmpty", parent=styles["BodyText"], fontName="Helvetica-Oblique"
        ),
    }


def _style_at_level(base_style, level: int):
    from reportlab.lib.units import cm

    return base_style.clone(
        f"{base_style.name}L{level}", leftIndent=level * INDENT_STEP_CM * cm
    )


def _render_node(node: FieldNode, level: int, field_styles: dict) -> list:
    from xml.sax.saxutils import escape

    from reportlab.platypus import Paragraph

    if node.kind == "group":
        flowables = [
            Paragraph(escape(node.label), _style_at_level(field_styles["group_title"], level))
        ]
        for child in node.children:
            flowables.extend(_render_node(child, level + 1, field_styles))
        return flowables

    if node.kind == "chips":
        text = ", ".join(escape(chip) for chip in node.chips)
    else:
        text = escape(node.text if node.text is not None else "—")

    return [
        Paragraph(
            f"<b>{escape(node.label)}:</b> {text}",
            _style_at_level(field_styles["field"], level),
        )
    ]


def build_respostas_flowables(respostas_json: dict | None, field_styles: dict) -> list:
    from reportlab.platypus import Paragraph

    tree = build_response_tree(respostas_json)
    if not tree:
        return [Paragraph(EMPTY_RESPONSE_MESSAGE, field_styles["empty"])]

    flowables: list = []
    for node in tree:
        flowables.extend(_render_node(node, level=0, field_styles=field_styles))
    return flowables
