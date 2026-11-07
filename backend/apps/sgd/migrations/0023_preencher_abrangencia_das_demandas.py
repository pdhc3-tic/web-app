"""Preenche `estado_sigla`/`territorio` das demandas existentes com o território
ATUAL do solicitante — mesmo critério de `resolver_nivel_do_usuario`
(apps/sgp/services/budget.py), replicado aqui com os modelos históricos.

A atividade não entra no critério. Lista no stdout as demandas que mudam de
Articulador (UF gravada diferente da UF do município da atividade, que era o
critério antigo); entre elas, as de solicitante sem nível resolvível, que
ficam no nível nacional (sem território). Rodar de novo recalcula tudo.
"""
from django.db import migrations

NIVEL_GLOBAL = {"super-admin", "ugp"}


def _uf_do_territorio(territorio):
    """Estado-sede (`estados[0]`), como `resolver_nivel_do_usuario`."""
    estados = territorio.estados or []
    return estados[0] if estados else None


def _abrangencia(perfis):
    """(estado_sigla, territorio) ou None quando não há nível resolvível."""
    slugs = {p.perfil.slug for p in perfis}
    if slugs & NIVEL_GLOBAL:
        return None, None
    for p in perfis:
        if p.perfil.slug == "articulador-estadual" and p.territorio is not None and p.territorio.estados:
            return p.territorio.estados[0], None
    for p in perfis:
        if p.perfil.slug == "adt-acr" and p.territorio is not None:
            return _uf_do_territorio(p.territorio), p.territorio
    return None


def preencher(apps, schema_editor):
    Demand = apps.get_model("sgd", "Demand")
    UserProfile = apps.get_model("core", "UserProfile")

    perfis_por_usuario = {}
    for perfil in UserProfile.objects.select_related("perfil", "territorio").order_by("pk"):
        perfis_por_usuario.setdefault(perfil.user_id, []).append(perfil)

    demandas = list(Demand.objects.select_related("activity__municipio__state"))
    mudaram, sem_nivel = [], []
    for demanda in demandas:
        uf_atividade = demanda.activity.municipio.state.sigla
        resolvido = _abrangencia(perfis_por_usuario.get(demanda.solicitante_id, []))
        if resolvido is None:
            # Sem nível do solicitante: só o território dele conta, então
            # fica no nível nacional.
            resolvido = (None, None)
            sem_nivel.append(demanda)
        demanda.estado_sigla, demanda.territorio = resolvido
        if demanda.estado_sigla != uf_atividade:
            mudaram.append((demanda, uf_atividade))

    Demand.objects.bulk_update(demandas, ["estado_sigla", "territorio"], batch_size=500)

    if mudaram:
        print(f"\n  [sgd 0023] {len(mudaram)} demanda(s) mudam de Articulador:")
        for demanda, uf_antiga in mudaram:
            print(
                f"    - demanda #{demanda.pk} ({demanda.status}): "
                f"{uf_antiga or '—'} -> {demanda.estado_sigla or 'nacional'}"
            )
    if sem_nivel:
        ids = ", ".join(f"#{d.pk}" for d in sem_nivel)
        print(f"  [sgd 0023] {len(sem_nivel)} demanda(s) de solicitante sem nível resolvível, no nível nacional: {ids}")


class Migration(migrations.Migration):

    dependencies = [
        ("sgd", "0022_demand_abrangencia_territorial"),
    ]

    operations = [
        migrations.RunPython(preencher, migrations.RunPython.noop),
    ]
