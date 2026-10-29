import ast
from pathlib import Path

RAIZ_SGD = Path(__file__).resolve().parent.parent
PORTA_ORCAMENTO = RAIZ_SGD / "services" / "orcamento.py"
MOTOR_DO_SGP = {"apps.sgp.services.budget", "apps.sgp.models.budget"}


def _modulos_importados(arquivo: Path) -> set[str]:
    # AST, não busca de texto: docstring ou comentário citando o módulo não conta.
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    modulos = set()
    for node in ast.walk(arvore):
        if isinstance(node, ast.Import):
            modulos.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modulos.add(node.module)
            # `from apps.sgp.services import budget` importa o submódulo pelo nome.
            modulos.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modulos


def _arquivos_do_sgd(*subpasta: str) -> list[Path]:
    return [
        arquivo for arquivo in RAIZ_SGD.joinpath(*subpasta).rglob("*.py")
        if not {"tests", "migrations"} & set(arquivo.relative_to(RAIZ_SGD).parts)
    ]


def _infratores(arquivos, proibido) -> dict[str, list[str]]:
    encontrados = {
        str(arquivo.relative_to(RAIZ_SGD)): sorted(m for m in _modulos_importados(arquivo) if proibido(m))
        for arquivo in arquivos
    }
    return {arquivo: modulos for arquivo, modulos in encontrados.items() if modulos}


def test_so_a_porta_de_orcamento_importa_o_motor_do_sgp():
    arquivos = [a for a in _arquivos_do_sgd() if a != PORTA_ORCAMENTO]
    assert _infratores(arquivos, lambda m: m in MOTOR_DO_SGP) == {}


def test_a_porta_de_orcamento_e_quem_importa_o_motor():
    # Garante que o teste acima enxerga os imports e não passa por vazio.
    assert _modulos_importados(PORTA_ORCAMENTO) >= MOTOR_DO_SGP


def _e_do_drf(modulo: str) -> bool:
    return modulo == "rest_framework" or modulo.startswith("rest_framework.")


def test_servicos_do_sgd_nao_importam_o_drf():
    assert _infratores(_arquivos_do_sgd("services"), _e_do_drf) == {}


def test_saldo_individual_nao_e_lido_do_audit_log():
    """O AuditLog é só auditoria: `balance.py` grava eventos, mas o estado da
    reserva vem de `DemandRequest`."""
    arvore = ast.parse((RAIZ_SGD / "services" / "balance.py").read_text(encoding="utf-8"))
    usos = {
        node.attr for node in ast.walk(arvore)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute) and node.value.attr == "objects"
        and isinstance(node.value.value, ast.Name) and node.value.value.id == "AuditLog"
    }
    assert usos == {"create"}
