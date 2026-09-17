"""
Funções puras de correspondência de nomes usadas para migrar
`Activity.parceiros` (texto livre) para o M2M `parceiros_organizacoes`
(Issue #228).

Sem dependência de Django/DB — testáveis isoladamente e reaproveitadas
pela data migration `0025_migra_parceiros_para_organizacoes`.
"""
import re
import unicodedata

_PONTUACAO = re.compile(r"[.,;:!?()\"']")
_ESPACOS = re.compile(r"\s+")
_SEPARADORES = re.compile(r"[;\n]+")


def normalizar_nome(texto: str) -> str:
    """Remove acentos e pontuação, colapsa espaços e normaliza a caixa."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto or "")
        if not unicodedata.combining(c)
    )
    sem_pontuacao = _PONTUACAO.sub(" ", sem_acento)
    return _ESPACOS.sub(" ", sem_pontuacao).strip().lower()


def dividir_parceiros_texto(texto: str) -> list[str]:
    """Separa o texto livre de `parceiros` em nomes individuais."""
    if not texto:
        return []
    return [parte.strip() for parte in _SEPARADORES.split(texto) if parte.strip()]


def _palavras_casam(palavra_livre: str, palavra_organizacao: str) -> bool:
    if palavra_livre == palavra_organizacao:
        return True
    return len(palavra_livre) >= 3 and palavra_organizacao.startswith(palavra_livre)


def nomes_equivalentes(nome_livre: str, nome_organizacao: str) -> bool:
    """
    Compara dois nomes palavra a palavra após normalizar, aceitando que uma
    palavra do texto livre seja abreviação (prefixo) da palavra correspondente
    no nome da organização — ex.: "assoc." casa com "associação".
    """
    palavras_livre = normalizar_nome(nome_livre).split()
    palavras_organizacao = normalizar_nome(nome_organizacao).split()
    if not palavras_livre or len(palavras_livre) != len(palavras_organizacao):
        return False
    return all(
        _palavras_casam(pl, po)
        for pl, po in zip(palavras_livre, palavras_organizacao)
    )


def casar_parceiros(
    nomes_livres: list[str], organizacoes: list[tuple[int, str]]
) -> tuple[list[int], list[str]]:
    """
    Tenta casar cada nome livre com uma organização.

    Retorna (ids_casados, nomes_nao_casados). Nenhuma entrada de
    `nomes_livres` é descartada: ela termina em exatamente uma das duas
    listas de retorno.
    """
    ids_casados = []
    nomes_nao_casados = []
    for nome in nomes_livres:
        organizacao_id = next(
            (
                org_id for org_id, org_nome in organizacoes
                if nomes_equivalentes(nome, org_nome)
            ),
            None,
        )
        if organizacao_id is not None:
            ids_casados.append(organizacao_id)
        else:
            nomes_nao_casados.append(nome)
    return ids_casados, nomes_nao_casados
