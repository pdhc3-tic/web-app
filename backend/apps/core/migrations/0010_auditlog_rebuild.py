# Migration manual — Issue #38
# Reconstrói o model AuditLog com os campos definitivos,
# índices compostos e trigger PostgreSQL de imutabilidade.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


CREATE_IMMUTABLE_TRIGGER = """
CREATE OR REPLACE FUNCTION core_auditlog_block_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION
            'Operação proibida: registros de AuditLog são imutáveis e não podem ser alterados. (operação: UPDATE, id: %)',
            OLD.id;
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'Operação proibida: registros de AuditLog são imutáveis e não podem ser removidos. (operação: DELETE, id: %)',
            OLD.id;
    END IF;
    RETURN NULL;
END;
$$;

CREATE TRIGGER core_auditlog_immutable
BEFORE UPDATE OR DELETE
ON core_auditlog
FOR EACH ROW
EXECUTE FUNCTION core_auditlog_block_mutation();
"""

DROP_IMMUTABLE_TRIGGER = """
DROP TRIGGER IF EXISTS core_auditlog_immutable ON core_auditlog;
DROP FUNCTION IF EXISTS core_auditlog_block_mutation();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_merge_0008_loginattempt_0008_userprofile'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # 1. Remove a tabela AuditLog legada (criada na 0007 com campos antigos)
        migrations.DeleteModel(
            name='AuditLog',
        ),

        # 2. Recria com a estrutura definitiva
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acao', models.CharField(max_length=50, verbose_name='Ação')),
                ('modulo', models.CharField(max_length=100, verbose_name='Módulo')),
                ('entidade', models.CharField(max_length=100, verbose_name='Entidade')),
                ('entidade_id', models.CharField(blank=True, default='', max_length=255, verbose_name='ID da Entidade')),
                ('valores_anteriores', models.JSONField(blank=True, default=dict, verbose_name='Valores Anteriores')),
                ('valores_novos', models.JSONField(blank=True, default=dict, verbose_name='Valores Novos')),
                ('ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='Endereço IP')),
                ('user_agent', models.TextField(blank=True, default='', verbose_name='User-Agent')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Timestamp')),
                ('usuario', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='audit_logs',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Usuário',
                    db_index=False,
                )),
            ],
            options={
                'verbose_name': 'Log de Auditoria',
                'verbose_name_plural': 'Logs de Auditoria',
                'ordering': ['-timestamp'],
            },
        ),

        # 3. Índice composto (user_id, timestamp DESC)
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(
                fields=['usuario', '-timestamp'],
                name='idx_auditlog_user_timestamp',
            ),
        ),

        # 4. Índice composto (entidade, entidade_id, timestamp DESC)
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(
                fields=['entidade', 'entidade_id', '-timestamp'],
                name='idx_auditlog_entidade_ts',
            ),
        ),

        # 5. Trigger PostgreSQL — bloqueia UPDATE e DELETE direto no banco
        migrations.RunSQL(
            sql=CREATE_IMMUTABLE_TRIGGER,
            reverse_sql=DROP_IMMUTABLE_TRIGGER,
        ),
    ]