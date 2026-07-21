from django.db import migrations


CULTURAS = [
    {"nome": "Arroz", "categoria": "graos", "ciclo": "anual"},
    {"nome": "Feijão Carioca", "nome_cientifico": "Phaseolus vulgaris", "categoria": "graos", "ciclo": "anual"},
    {"nome": "Feijão de Corda", "nome_cientifico": "Vigna unguiculata", "categoria": "graos", "ciclo": "anual"},
    {"nome": "Feijão Franco", "nome_cientifico": "Phaseolus vulgaris", "categoria": "graos", "ciclo": "anual"},
    {"nome": "Feijão Mulatinho", "categoria": "graos", "ciclo": "anual"},
    {"nome": "Milho", "categoria": "graos", "ciclo": "anual"},
    {"nome": "Sorgo", "categoria": "graos", "ciclo": "anual"},
    {"nome": "Guandu", "categoria": "graos", "ciclo": "anual"},
    {"nome": "Cevada", "categoria": "graos", "ciclo": "anual"},
    {"nome": "Aveia", "categoria": "graos", "ciclo": "anual"},
    {"nome": "Mandioca", "categoria": "raizes", "ciclo": "perene"},
    {"nome": "Batata", "categoria": "raizes", "ciclo": "anual"},
    {"nome": "Inhame", "categoria": "raizes", "ciclo": "anual"},
    {"nome": "Cará", "categoria": "raizes", "ciclo": "anual"},
    {"nome": "Nabo", "categoria": "raizes", "ciclo": "bianual"},
    {"nome": "Mandioquinha", "categoria": "raizes", "ciclo": "anual"},
    {"nome": "Banana", "categoria": "frutas", "ciclo": "perene"},
    {"nome": "Manga", "categoria": "frutas", "ciclo": "perene"},
    {"nome": "Goiaba", "categoria": "frutas", "ciclo": "perene"},
    {"nome": "Caju", "categoria": "frutas", "ciclo": "perene"},
    {"nome": "Laranja", "categoria": "frutas", "ciclo": "perene"},
    {"nome": "Limão", "categoria": "frutas", "ciclo": "perene"},
    {"nome": "Abacaxi", "categoria": "frutas", "ciclo": "perene"},
    {"nome": "Coco", "categoria": "frutas", "ciclo": "perene"},
    {"nome": "Açaí", "categoria": "frutas", "ciclo": "perene"},
    {"nome": "Tomate", "categoria": "hortalicas", "ciclo": "anual"},
    {"nome": "Pimentão", "categoria": "hortalicas", "ciclo": "anual"},
    {"nome": "Alface", "categoria": "hortalicas", "ciclo": "anual"},
    {"nome": "Repolho", "categoria": "hortalicas", "ciclo": "bianual"},
    {"nome": "Cebola", "categoria": "hortalicas", "ciclo": "bianual"},
    {"nome": "Alho", "categoria": "hortalicas", "ciclo": "bianual"},
    {"nome": "Pepino", "categoria": "hortalicas", "ciclo": "anual"},
    {"nome": "Abobrinha", "categoria": "hortalicas", "ciclo": "anual"},
    {"nome": "Berinjela", "categoria": "hortalicas", "ciclo": "anual"},
    {"nome": "Feijão Vagem", "categoria": "leguminosas", "ciclo": "anual"},
    {"nome": "Ervilha", "categoria": "leguminosas", "ciclo": "anual"},
    {"nome": "Amendoim", "categoria": "oleaginosas", "ciclo": "anual"},
    {"nome": "Soja", "categoria": "oleaginosas", "ciclo": "anual"},
    {"nome": "Girassol", "categoria": "oleaginosas", "ciclo": "anual"},
    {"nome": "Algodão", "categoria": "fibrosas", "ciclo": "anual"},
    {"nome": "Juta", "categoria": "fibrosas", "ciclo": "anual"},
    {"nome": "Sisal", "categoria": "fibrosas", "ciclo": "perene"},
    {"nome": "Capim Elefante", "categoria": "forrageiras", "ciclo": "perene"},
    {"nome": "Brachiaria", "categoria": "forrageiras", "ciclo": "perene"},
    {"nome": "Panicum", "categoria": "forrageiras", "ciclo": "perene"},
    {"nome": "Orquídea", "categoria": "ornamentais", "ciclo": "perene"},
    {"nome": "Antúrio", "categoria": "ornamentais", "ciclo": "perene"},
    {"nome": "Alecrim", "categoria": "medicinais", "ciclo": "perene"},
    {"nome": "Erva-cidreira", "categoria": "medicinais", "ciclo": "perene"},
    {"nome": "Aroeira", "categoria": "medicinais", "ciclo": "perene"},
    {"nome": "Maneirão", "categoria": "medicinais", "ciclo": "anual"},
    {"nome": "Cana-de-açúcar", "categoria": "outras", "ciclo": "perene"},
    {"nome": "Tabaco", "categoria": "outras", "ciclo": "anual"},
    {"nome": "Café", "categoria": "outras", "ciclo": "perene"},
    {"nome": "Cacau", "categoria": "outras", "ciclo": "perene"},
    {"nome": "Pimenta-do-reino", "categoria": "outras", "ciclo": "perene"},
    {"nome": "Jutaíba", "categoria": "outras", "ciclo": "perene"},
]

ESPECIES_ANIMAIS = [
    {"nome": "Nelore", "categoria": "bovino"},
    {"nome": "Angus", "categoria": "bovino"},
    {"nome": "Girolando", "categoria": "bovino"},
    {"nome": "Sindhi", "categoria": "bovino"},
    {"nome": "Guzerá", "categoria": "bovino"},
    {"nome": "Brahman", "categoria": "bovino"},
    {"nome": "Nepol", "categoria": "bovino"},
    {"nome": "Pardo Suíço", "categoria": "bovino"},
    {"nome": "Large Black", "categoria": "suino"},
    {"nome": "Landrace", "categoria": "suino"},
    {"nome": "Pietrain", "categoria": "suino"},
    {"nome": "Duroc", "categoria": "suino"},
    {"nome": "Cambuí", "categoria": "suino"},
    {"nome": "Bergamasca", "categoria": "ovino"},
    {"nome": "Santa Inês", "categoria": "ovino"},
    {"nome": "Somali", "categoria": "ovino"},
    {"nome": "Somali Preta", "categoria": "caprino"},
    {"nome": "Saanen", "categoria": "caprino"},
    {"nome": "Alpina", "categoria": "caprino"},
    {"nome": "Boer", "categoria": "caprino"},
    {"nome": "Canindé", "categoria": "caprino"},
    {"nome": "Cabra Mestiça", "categoria": "caprino"},
    {"nome": "Galinha Caipira", "categoria": "aves"},
    {"nome": "Galinha Poedeira", "categoria": "aves"},
    {"nome": "Galo de Combate", "categoria": "aves"},
    {"nome": "Pato", "categoria": "aves"},
    {"nome": "Pavao", "categoria": "aves"},
    {"nome": "Codorna", "categoria": "aves"},
    {"nome": "Mangalarga Marchador", "categoria": "equino"},
    {"nome": "Quarto de Milha", "categoria": "equino"},
    {"nome": "Crioulo", "categoria": "equino"},
    {"nome": "Tambaqui", "categoria": "piscicultura"},
    {"nome": "Tilápia", "categoria": "piscicultura"},
    {"nome": "Pirarucu", "categoria": "piscicultura"},
    {"nome": "Pacu", "categoria": "piscicultura"},
    {"nome": "Apis Mellifera", "categoria": "apicultura"},
    {"nome": "Caprino (corte)", "categoria": "outros"},
]


def seed_culturas(apps, schema_editor):
    Cultura = apps.get_model("sgp", "Cultura")
    for item in CULTURAS:
        Cultura.objects.update_or_create(
            nome=item["nome"],
            defaults={
                "nome_cientifico": item.get("nome_cientifico", ""),
                "categoria": item["categoria"],
                "ciclo": item["ciclo"],
                "ativa": True,
            },
        )


def seed_especies(apps, schema_editor):
    EspecieAnimal = apps.get_model("sgp", "EspecieAnimal")
    for item in ESPECIES_ANIMAIS:
        EspecieAnimal.objects.update_or_create(
            nome=item["nome"],
            defaults={
                "categoria": item["categoria"],
                "ativa": True,
            },
        )


def forwards(apps, schema_editor):
    seed_culturas(apps, schema_editor)
    seed_especies(apps, schema_editor)


def backwards(apps, schema_editor):
    Cultura = apps.get_model("sgp", "Cultura")
    EspecieAnimal = apps.get_model("sgp", "EspecieAnimal")
    Cultura.objects.filter(
        nome__in=[c["nome"] for c in CULTURAS],
    ).delete()
    EspecieAnimal.objects.filter(
        nome__in=[e["nome"] for e in ESPECIES_ANIMAIS],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sgp", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
