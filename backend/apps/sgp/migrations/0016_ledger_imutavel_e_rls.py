"""Fecha o ledger: saldo de pool não negativo, transações e remanejamentos só por INSERT e RLS nas
tabelas de saldo. `app_user`, o usuário de runtime, não é dono das tabelas: ENABLE basta, sem FORCE.

O RLS é um teto de segurança, mais permissivo que o escopo dos serviços. O Articulador também vê os
pools nacionais, porque o painel os mostra a ele, e a FGD vê tudo, porque conclui as demandas."""
from django.db import migrations, models
import django.db.models.expressions

BLOQUEAR_MUTACAO = """
CREATE OR REPLACE FUNCTION sgp_orcamento_bloquear_mutacao()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Operação proibida: registros de % são imutáveis; correções são novos lançamentos. (operação: %, id: %)',
        TG_TABLE_NAME, TG_OP, OLD.id;
END;
$$;

CREATE TRIGGER sgp_budgettransaction_imutavel
BEFORE UPDATE OR DELETE ON sgp_budgettransaction
FOR EACH ROW EXECUTE FUNCTION sgp_orcamento_bloquear_mutacao();

CREATE TRIGGER sgp_budgettransfer_imutavel
BEFORE UPDATE OR DELETE ON sgp_budgettransfer
FOR EACH ROW EXECUTE FUNCTION sgp_orcamento_bloquear_mutacao();
"""

LIBERAR_MUTACAO = """
DROP TRIGGER IF EXISTS sgp_budgettransfer_imutavel ON sgp_budgettransfer;
DROP TRIGGER IF EXISTS sgp_budgettransaction_imutavel ON sgp_budgettransaction;
DROP FUNCTION IF EXISTS sgp_orcamento_bloquear_mutacao();
"""

GLOBAL = "current_setting('app.user_role', true) IN ('ugp', 'fgd', 'super-admin')"
ARTICULADOR = "current_setting('app.user_role', true) = 'articulador-estadual'"
TERRITORIOS = "string_to_array(NULLIF(current_setting('app.user_territorios', true), ''), ',')::int[]"
USUARIO = "NULLIF(current_setting('app.current_user_id', true), '')::bigint"
# Sem território na sessão, o Articulador vê todos: o mesmo critério da política de sgd_demand.
# O cast faz da subconsulta um valor só: sem ele, `= ANY` compararia o texto com cada linha, que é um array.
ESTADOS_DO_ARTICULADOR = f"""(
    SELECT array_agg(DISTINCT estado) FROM core_territory t, unnest(t.estados) AS estado
    WHERE {TERRITORIOS} IS NULL OR t.id = ANY({TERRITORIOS})
)::varchar[]"""

VISIBILIDADE_DO_LIMITE = f"""
    {GLOBAL}
    OR sgp_spendinglimit.user_id = {USUARIO}
    OR (
        {ARTICULADOR} AND EXISTS (
            SELECT 1 FROM core_territory t
            WHERE t.id = sgp_spendinglimit.territorio_id AND t.estados && {ESTADOS_DO_ARTICULADOR}
        )
    )
"""

ATIVAR_RLS = f"""
ALTER TABLE sgp_budgetpool ENABLE ROW LEVEL SECURITY;
CREATE POLICY sgp_budgetpool_visibilidade ON sgp_budgetpool
FOR ALL
USING (
    {GLOBAL}
    OR (
        {ARTICULADOR} AND (
            sgp_budgetpool.nivel = 'nacional'
            OR EXISTS (
                SELECT 1 FROM core_state s
                WHERE s.id = sgp_budgetpool.estado_id AND s.sigla = ANY({ESTADOS_DO_ARTICULADOR})
            )
            OR EXISTS (
                SELECT 1 FROM core_territory t
                WHERE t.id = sgp_budgetpool.territorio_id AND t.estados && {ESTADOS_DO_ARTICULADOR}
            )
        )
    )
    OR (sgp_budgetpool.nivel = 'territorial' AND sgp_budgetpool.territorio_id = ANY({TERRITORIOS}))
);

ALTER TABLE sgp_spendinglimit ENABLE ROW LEVEL SECURITY;
CREATE POLICY sgp_spendinglimit_visibilidade ON sgp_spendinglimit
FOR ALL
USING ({VISIBILIDADE_DO_LIMITE});
-- O padrão do perfil é regra geral: todo usuário lê, para saber o próprio limite.
CREATE POLICY sgp_spendinglimit_padrao_legivel ON sgp_spendinglimit
FOR SELECT
USING (sgp_spendinglimit.escopo = 'perfil');

ALTER TABLE sgp_budgettransaction ENABLE ROW LEVEL SECURITY;
-- Mesmo critério do pool ou do limite referenciado: as subconsultas passam pelas políticas deles.
CREATE POLICY sgp_budgettransaction_visibilidade ON sgp_budgettransaction
FOR ALL
USING (
    EXISTS (SELECT 1 FROM sgp_budgetpool p WHERE p.id = sgp_budgettransaction.pool_id)
    OR EXISTS (SELECT 1 FROM sgp_spendinglimit l WHERE l.id = sgp_budgettransaction.spending_limit_id)
);
"""

DESATIVAR_RLS = """
DROP POLICY IF EXISTS sgp_budgettransaction_visibilidade ON sgp_budgettransaction;
ALTER TABLE sgp_budgettransaction DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sgp_spendinglimit_padrao_legivel ON sgp_spendinglimit;
DROP POLICY IF EXISTS sgp_spendinglimit_visibilidade ON sgp_spendinglimit;
ALTER TABLE sgp_spendinglimit DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sgp_budgetpool_visibilidade ON sgp_budgetpool;
ALTER TABLE sgp_budgetpool DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('sgp', '0015_preencher_ledger'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='budgetpool',
            constraint=models.CheckConstraint(condition=models.Q(('valor_alocado__gte', django.db.models.expressions.CombinedExpression(models.F('valor_comprometido'), '+', models.F('valor_executado')))), name='ck_budget_pool_saldo_nao_negativo'),
        ),
        migrations.RunSQL(sql=BLOQUEAR_MUTACAO, reverse_sql=LIBERAR_MUTACAO),
        migrations.RunSQL(sql=ATIVAR_RLS, reverse_sql=DESATIVAR_RLS),
    ]
