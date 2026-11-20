"""RLS em sgp_ufpa — matriz do Core (Requisitos-CORE §2.1, "SGP — UFPAs"):

    Agricultor: Própria · ADT/ACR: CRUD territorial · Articulador: Leitura (estados vinculados)
    UGP: Leitura · FGD: — · Super Admin: Total

A política resolve o escopo direto de `core_userprofile` a partir de
`app.current_user_id`, sem ler `app.user_role`. Por isso:
- `visao_total()` do orçamento (que troca só `app.user_role`) não amplia o acesso a UFPAs;
- um usuário com vários perfis recebe a união dos escopos;
- sem contexto (`app.current_user_id` vazio), nada é visível nem gravável.

Um vínculo ausente não vira acesso global: o ADT/ACR só alcança os territórios
dos próprios perfis `adt-acr`, e o Articulador só os estados dos territórios dos
próprios perfis `articulador-estadual`. "Própria" do Agricultor fica pendente: o
modelo ainda não liga User a UFPA (docs/decisoes-modelo-dados.md §12).

`app.ufpa_sistema = 'on'` libera a tabela para operações de sistema já
autorizadas em Python (`apps.core.db_context.acesso_de_sistema_ufpa`).

`app_user`, o usuário de runtime, não é dono da tabela (as migrations rodam como
`postgres`) e não tem BYPASSRLS: ENABLE basta, sem FORCE.

Não toca em dados: reverter e reaplicar só remove e recria as políticas."""
from django.db import migrations

USUARIO = "NULLIF(current_setting('app.current_user_id', true), '')::bigint"
SISTEMA = "current_setting('app.ufpa_sistema', true) = 'on'"


def _tem_perfil(*slugs):
    lista = ", ".join(f"'{slug}'" for slug in slugs)
    return f"""EXISTS (
        SELECT 1 FROM core_userprofile up JOIN core_role r ON r.id = up.perfil_id
        WHERE up.user_id = {USUARIO} AND r.slug IN ({lista})
    )"""


def _territorios_do_perfil(slug):
    # Subconsulta sem correlação com a linha: o Postgres a avalia uma vez por query.
    # O cast faz dela um valor só: sem ele, `= ANY` compararia o id com cada linha, que é um array.
    return f"""(
        SELECT array_agg(up.territorio_id) FROM core_userprofile up JOIN core_role r ON r.id = up.perfil_id
        WHERE up.user_id = {USUARIO} AND r.slug = '{slug}' AND up.territorio_id IS NOT NULL
    )::bigint[]"""


TOTAL = f"""(
    {_tem_perfil('super-admin')}
    OR EXISTS (SELECT 1 FROM core_user u WHERE u.id = {USUARIO} AND u.is_superuser)
)"""
GLOBAL_LEITURA = f"({TOTAL} OR {_tem_perfil('ugp')})"
ADT = f"(sgp_ufpa.territorio_id = ANY({_territorios_do_perfil('adt-acr')}))"
ESTADOS_DO_ARTICULADOR = f"""(
    SELECT array_agg(DISTINCT estado) FROM core_territory t, unnest(t.estados) AS estado
    WHERE t.id = ANY({_territorios_do_perfil('articulador-estadual')})
)::varchar[]"""
ARTICULADOR = f"""EXISTS (
    SELECT 1 FROM core_municipality m JOIN core_state s ON s.id = m.state_id
    WHERE m.id = sgp_ufpa.municipio_id AND s.sigla = ANY({ESTADOS_DO_ARTICULADOR})
)"""

LEITURA = f"({SISTEMA} OR {GLOBAL_LEITURA} OR {ADT} OR {ARTICULADOR})"
ESCRITA = f"({SISTEMA} OR {TOTAL} OR {ADT})"

POLITICAS = (
    "sgp_ufpa_leitura",
    "sgp_ufpa_insercao",
    "sgp_ufpa_alteracao",
    "sgp_ufpa_exclusao",
)

ATIVAR_RLS = f"""
ALTER TABLE sgp_ufpa ENABLE ROW LEVEL SECURITY;

CREATE POLICY sgp_ufpa_leitura ON sgp_ufpa
FOR SELECT
USING {LEITURA};

CREATE POLICY sgp_ufpa_insercao ON sgp_ufpa
FOR INSERT
WITH CHECK {ESCRITA};

-- USING decide quais linhas podem ser alteradas; WITH CHECK, como elas podem ficar:
-- o ADT não move uma UFPA para um território fora do próprio escopo.
CREATE POLICY sgp_ufpa_alteracao ON sgp_ufpa
FOR UPDATE
USING {ESCRITA}
WITH CHECK {ESCRITA};

CREATE POLICY sgp_ufpa_exclusao ON sgp_ufpa
FOR DELETE
USING {ESCRITA};
"""

DESATIVAR_RLS = "".join(f"DROP POLICY IF EXISTS {nome} ON sgp_ufpa;\n" for nome in POLITICAS) + (
    "ALTER TABLE sgp_ufpa DISABLE ROW LEVEL SECURITY;\n"
)


class Migration(migrations.Migration):

    dependencies = [
        # As tabelas do core citadas (userprofile, role, user, territory,
        # municipality, state) já existem: sgp 0001 depende de core 0021.
        ("sgp", "0021_renomeia_upf_para_ufpa"),
    ]

    operations = [
        migrations.RunSQL(sql=ATIVAR_RLS, reverse_sql=DESATIVAR_RLS),
    ]
