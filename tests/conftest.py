import pytest

from backend.shared import stock_ledger


@pytest.fixture(autouse=True)
def inventario_simulado_en_memoria(monkeypatch):
    """Aísla las pruebas del stock real compartido en Redis."""
    monkeypatch.setattr(stock_ledger, "_redis_ok", False)
    monkeypatch.setattr(stock_ledger, "_memory", {})
