from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from packages.galaxy_agent.artifacts import ArtifactStore
from packages.galaxy_agent.models import AnalyzeRequest, Target
from packages.galaxy_agent.orchestrator import TaskOrchestrator
from packages.galaxy_core.analyzer import BasicGalaxyAnalyzer


class _InMemoryArtifactStore(ArtifactStore):
    """ArtifactStore de pruebas: guarda solo las imágenes en memoria.

    No nos importa el sistema de archivos aquí; solo queremos comprobar que
    el orquestador acaba llamando a save_image con algún contenido binario.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        super().__init__(base_dir="artifacts-test")
        self.saved_images: dict[str, bytes] = {}

    def save_image(self, request_id: str, image_bytes: bytes) -> str:  # type: ignore[override]
        self.saved_images[request_id] = image_bytes
        # Path ficticio; el orquestador solo lo reinyecta en image_url.
        return f"memory://{request_id}/image.jpg"


def _make_request(
    request_id: str = "req-1",
    target_name: str | None = "M81",
    options: dict[str, Any] | None = None,
) -> AnalyzeRequest:
    return AnalyzeRequest(
        request_id=request_id,
        message=None,
        messages=None,
        target=Target(name=target_name) if target_name is not None else None,
        task="measure_basic",
        image_url=None,
        options=options or {},
    )


def _fake_response() -> Any:
    class Resp:
        status_code = 200
        text = ""

        def __init__(self) -> None:
            arr = np.zeros((2, 2), dtype=np.uint8)
            self.content = arr.tobytes()

        def raise_for_status(self) -> None:
            return None

    return Resp()


def test_visible_band_prefers_sdss_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """band=visible debe intentar primero catalog=SDSS y guardar una imagen."""

    calls: list[dict[str, Any]] = []

    def fake_resolve_and_fetch(**kwargs: Any) -> Any:
        calls.append(kwargs)

        class Resolved:
            ra_deg = 150.0
            dec_deg = 2.0
            image_url = "https://example.org/sdss.png"

        return Resolved()

    monkeypatch.setattr(
        "packages.galaxy_agent.orchestrator.resolve_and_fetch",
        fake_resolve_and_fetch,
    )
    monkeypatch.setattr(
        "packages.galaxy_agent.orchestrator.requests.get",
        lambda url, timeout, verify: _fake_response(),
    )

    store = _InMemoryArtifactStore()
    orchestrator = TaskOrchestrator(BasicGalaxyAnalyzer(), store)

    req = _make_request(
        request_id="req-visible",
        target_name="M81",
        options={"band": "visible"},
    )

    updated = orchestrator._resolve_fetch_and_download(req)

    assert calls, "resolve_and_fetch debería haberse llamado al menos una vez"
    first_call = calls[0]
    assert first_call.get("catalog") == "SDSS"
    assert first_call.get("band") is None

    assert updated.image_url == "memory://req-visible/image.jpg"
    assert store.saved_images["req-visible"]


def test_infrared_band_usa_mapping_de_band(monkeypatch: pytest.MonkeyPatch) -> None:
    """band=infrared debe delegar en el mapeo de banda (sin forzar SDSS)."""

    calls: list[dict[str, Any]] = []

    def fake_resolve_and_fetch(**kwargs: Any) -> Any:
        calls.append(kwargs)

        class Resolved:
            ra_deg = 148.888
            dec_deg = 69.065
            image_url = "https://example.org/infrared.png"

        return Resolved()

    monkeypatch.setattr(
        "packages.galaxy_agent.orchestrator.resolve_and_fetch",
        fake_resolve_and_fetch,
    )
    monkeypatch.setattr(
        "packages.galaxy_agent.orchestrator.requests.get",
        lambda url, timeout, verify: _fake_response(),
    )

    store = _InMemoryArtifactStore()
    orchestrator = TaskOrchestrator(BasicGalaxyAnalyzer(), store)

    req = _make_request(
        request_id="req-ir",
        target_name="M81",
        options={"band": "infrared"},
    )

    updated = orchestrator._resolve_fetch_and_download(req)

    assert calls, "resolve_and_fetch debería haberse llamado al menos una vez"
    first_call = calls[0]
    # Para infrared no forzamos SDSS; se usa exclusivamente band.
    assert first_call.get("catalog") is None
    assert first_call.get("band") == "infrared"

    assert updated.image_url == "memory://req-ir/image.jpg"
    assert store.saved_images["req-ir"]


def test_visible_band_fallback_si_sdss_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si SDSS falla para visible, debe intentarse el siguiente survey de la banda."""

    calls: list[dict[str, Any]] = []

    def fake_resolve_and_fetch(**kwargs: Any) -> Any:
        calls.append(kwargs)
        # Primer intento (SDSS) falla, segundo (band-mapped) tiene éxito.
        if len(calls) == 1:
            raise RuntimeError("Simulated SDSS failure")

        class Resolved:
            ra_deg = 150.0
            dec_deg = 2.0
            image_url = "https://example.org/fallback.png"

        return Resolved()

    monkeypatch.setattr(
        "packages.galaxy_agent.orchestrator.resolve_and_fetch",
        fake_resolve_and_fetch,
    )
    monkeypatch.setattr(
        "packages.galaxy_agent.orchestrator.requests.get",
        lambda url, timeout, verify: _fake_response(),
    )

    store = _InMemoryArtifactStore()
    orchestrator = TaskOrchestrator(BasicGalaxyAnalyzer(), store)

    req = _make_request(
        request_id="req-visible-fallback",
        target_name="M81",
        options={"band": "visible"},
    )

    updated = orchestrator._resolve_fetch_and_download(req)

    # Debe haber al menos dos intentos de resolución.
    assert len(calls) >= 2
    assert updated.image_url == "memory://req-visible-fallback/image.jpg"
    assert store.saved_images["req-visible-fallback"]

