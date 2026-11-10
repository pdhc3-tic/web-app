# Substitui a política de `0004_rls_demand`: o critério territorial do
# Articulador passa a ser `sgd_demand.estado_sigla` (território do solicitante,
# congelado na criação — Issue #352), sem JOIN com sgp_activity/core_*.
# Demanda nacional (estado_sigla nulo) não é vista por nenhum Articulador.
from django.db import migrations

_TERRITORIOS_DO_USUARIO = """
    CASE
        WHEN NULLIF(current_setting('app.user_territorios', true), '') IS NULL
            THEN (SELECT array_agg(id) FROM core_territory)
        ELSE string_to_array(current_setting('app.user_territorios', true), ',')::int[]
    END
"""

NOVA_POLITICA_SQL = f"""
DROP POLICY IF EXISTS sgd_demand_visibilidade ON sgd_demand;

CREATE POLICY sgd_demand_visibilidade ON sgd_demand
FOR ALL
USING (
    current_setting('app.user_role', true) IN ('ugp', 'fgd', 'super-admin')
    OR solicitante_id = NULLIF(current_setting('app.current_user_id', true), '')::int
    OR (
        current_setting('app.user_role', true) = 'articulador-estadual'
        AND sgd_demand.estado_sigla IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM core_territory t
            WHERE t.id = ANY({_TERRITORIOS_DO_USUARIO})
              AND t.estados @> ARRAY[sgd_demand.estado_sigla]::varchar[]
        )
    )
);
"""

POLITICA_ANTIGA_SQL = f"""
DROP POLICY IF EXISTS sgd_demand_visibilidade ON sgd_demand;

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
                  WHERE t.id = ANY({_TERRITORIOS_DO_USUARIO})
                  AND t.estados @> ARRAY[s.sigla]::varchar[]
              )
        )
    )
);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("sgd", "0023_preencher_abrangencia_das_demandas"),
    ]

    operations = [
        migrations.RunSQL(sql=NOVA_POLITICA_SQL, reverse_sql=POLITICA_ANTIGA_SQL),
    ]
