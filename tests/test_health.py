"""
Testes para os endpoints de health check.
"""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Testa se o endpoint /health retorna status healthy."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_readiness_check(client: TestClient) -> None:
    """Testa se o endpoint /ready retorna status ready."""
    response = client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "version" in data
    assert "services" in data


def test_health_response_format(client: TestClient) -> None:
    """Testa o formato da resposta do health check."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Verifica que tem exatamente os campos esperados
    assert set(data.keys()) == {"status", "version"}
    assert isinstance(data["status"], str)
    assert isinstance(data["version"], str)


def test_readiness_services_format(client: TestClient) -> None:
    """Testa o formato dos serviços no readiness check."""
    response = client.get("/ready")

    assert response.status_code == 200
    data = response.json()

    services = data["services"]
    expected_services = ["azure_openai", "azure_search", "azure_storage", "cosmos_db"]

    for service in expected_services:
        assert service in services
