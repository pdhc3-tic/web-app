# RLS em sgd_demand — 2_Arquitetura_Tecnica_v1_1.md §3.2: solicitante vê as
# próprias, Articulador vê do estado, UGP/FGD/super-admin veem todas.
# `app_user` (usuário de runtime, backend/db/init/01_app_user.sql) não é
# dono da tabela — ENABLE basta, sem precisar de FORCE.
#
# Teto de segurança (defesa em profundidade): mais permissivo pro
# Articulador do que `demand_visibility_scope` em Python (que ainda restringe
# a "Submetidas + próprias + já decididas" via RF18) — a política aqui só
# garante o critério territorial, igual descrito no documento.
from django.db import migrations

ENABLE_RLS_SQL = """
ALTER TABLE sgd_demand ENABLE ROW LEVEL SECURITY;

CREATE POLICY sgd_demand_visibilidade ON sgd_demand
FOR ALL
USING (
    current_setting('app.user_role', true) IN ('ugp', 'fgd', 'super-admin')
    OR solicitante_id = NULLIF(current_setting('app.current_user_id', true), '')::int
    OR (
        current_setting('app.user_role', true) = 'articulador-estadual'
        AND EXISTS (
            SELECT 1 FROM sgp_activity a
            JOIN core_municipality m ON m.id = a.municipio_id
            JOIN core_state s ON s.id = m.state_id
            WHERE a.id = sgd_demand.activity_id
              AND EXISTS (
                  SELECT 1 FROM core_territory t
                  WHERE t.id = ANY(
                      CASE
                          WHEN NULLIF(current_setting('app.user_territorios', true), '') IS NULL
                              THEN (SELECT array_agg(id) FROM core_territory)
                          ELSE string_to_array(current_setting('app.user_territorios', true), ',')::int[]
                      END
                  )
                  AND t.estados @> ARRAY[s.sigla]::varchar[]
              )
        )
    )
);
"""

DISABLE_RLS_SQL = """
DROP POLICY IF EXISTS sgd_demand_visibilidade ON sgd_demand;
ALTER TABLE sgd_demand DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        # sgd 0001 já depende de sgp 0028+ (tabelas sgp_activity/core_* já
        # existem transitivamente nesse ponto do grafo de migrations).
        ('sgd', '0003_demanddocument_fornecedor'),
    ]

    operations = [
        migrations.RunSQL(sql=ENABLE_RLS_SQL, reverse_sql=DISABLE_RLS_SQL),
    ]
