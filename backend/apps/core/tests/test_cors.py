import pytest


@pytest.mark.django_db
def test_nome_do_arquivo_exportado_chega_ao_frontend_de_outra_origem(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]

    resposta = client.get("/api/v1/notifications/me/", HTTP_ORIGIN="http://localhost:3000")

    assert resposta["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert resposta["Access-Control-Expose-Headers"] == "Content-Disposition"
