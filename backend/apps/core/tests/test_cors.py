import pytest


def _expostos(resposta) -> set[str]:
    return {cabecalho.strip() for cabecalho in resposta["Access-Control-Expose-Headers"].split(",")}


@pytest.mark.django_db
def test_nome_do_arquivo_exportado_chega_ao_frontend_de_outra_origem(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]

    resposta = client.get("/api/v1/notifications/me/", HTTP_ORIGIN="http://localhost:3000")

    assert resposta["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert "Content-Disposition" in _expostos(resposta)


@pytest.mark.django_db
def test_aviso_de_rota_depreciada_chega_ao_frontend_de_outra_origem(client, settings):
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]

    resposta = client.get("/api/v1/notifications/me/", HTTP_ORIGIN="http://localhost:3000")

    assert {"Deprecation", "Link"} <= _expostos(resposta)
