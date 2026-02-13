from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from packages.galaxy_agent.domain.models import TaskType, Target
from packages.galaxy_agent.models import AnalyzeRequest


class LangChainBackend:
    """Backend para integrar un LLM (OpenAI) con el agente.

    MVP: usa el LLM solo para convertir lenguaje natural → parámetros estructurados
    (target/options) que luego consume el TaskOrchestrator. No ejecuta todavía
    tool-calling completo; en su lugar, pide al modelo que devuelva un JSON.
    """

    def __init__(self) -> None:
        self._model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        # El cliente usa OPENAI_API_KEY del entorno (no lo leemos aquí directamente).
        self._client = OpenAI()

    def enrich_request(self, request: AnalyzeRequest) -> AnalyzeRequest:
        """Usar el LLM para rellenar target/options a partir de mensajes NL.

        - Si ya viene target+task → no hace nada (devuelve el request tal cual).
        - Si no hay mensajes → tampoco hace nada.
        - Si hay mensajes NL y falta target/task → pide al LLM que extraiga:
          name, ra_deg/dec_deg, band, size_arcmin y construye un nuevo AnalyzeRequest.
        """
        if request.target is not None and request.task is not None:
            return request

        messages = request.get_normalized_messages()
        if not messages:
            return request

        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is required for natural language requests. "
                "Set it in .env and restart the container (or process)."
            )

        # Unir el historial en un solo texto sencillo para este MVP.
        conversation = "\n".join(f"{m.role}: {m.content}" for m in messages)

        system_prompt = (
            "You are an assistant that extracts structured parameters for a galaxy imaging task.\n"
            "The user will describe what galaxy image they want (by name or coordinates),"
            " which band (visible, infrared, uv) and optionally the field of view in arcminutes.\n"
            "Return ONLY a JSON object with the following keys:\n"
            "- name: string or null (galaxy name, e.g. 'M51').\n"
            "- ra_deg: number or null (right ascension in degrees).\n"
            "- dec_deg: number or null (declination in degrees).\n"
            "- band: 'visible', 'infrared', 'uv' or null.\n"
            "- size_arcmin: number (field of view in arcminutes, default 10.0 if not specified).\n"
            "If both name and coordinates are present, prefer the coordinates but still return the name.\n"
            "If the user does not specify some fields, set them to null (or 10.0 for size_arcmin).\n"
        )

        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": conversation},
            ],
        )

        content = response.choices[0].message.content or "{}"
        try:
            data: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError:
            return request

        name = data.get("name")
        ra_deg = data.get("ra_deg")
        dec_deg = data.get("dec_deg")
        band = data.get("band")
        size_arcmin = 10.0
        if data.get("size_arcmin") is not None:
            try:
                size_arcmin = float(data["size_arcmin"])
            except (TypeError, ValueError):
                pass

        options = dict(request.options) if request.options else {}
        if ra_deg is not None and dec_deg is not None:
            try:
                options["ra_deg"] = float(ra_deg)
                options["dec_deg"] = float(dec_deg)
            except (TypeError, ValueError):
                pass
        if band:
            options["band"] = str(band)
        options.setdefault("size_arcmin", size_arcmin)

        target = request.target
        if target is None and name:
            target = Target(name=str(name))

        task: TaskType | None = request.task or "morphology_summary"

        return AnalyzeRequest(
            request_id=request.request_id,
            message=request.message,
            messages=request.messages,
            target=target,
            task=task,
            image_url=request.image_url,
            options=options,
        )

    def build_prompt(self, request: AnalyzeRequest) -> str:
        """Mantener un helper simple de prompt (útil para debug o futuros usos)."""
        target_name = request.target.name if request.target else "unknown"
        task = request.task or "morphology_summary"
        return (
            "You are a galaxy analysis assistant. "
            f"Task={task}, target={target_name}, "
            f"request_id={request.request_id}."
        )

    def plan_tool_calls(self, request: AnalyzeRequest) -> list[str]:
        """Mapa estático task → tools, útil como guía/documentación."""
        task_to_tools = {
            "segment": ["tool_segment"],
            "measure_basic": ["tool_segment", "tool_measure_basic"],
            "morphology_summary": [
                "tool_segment",
                "tool_measure_basic",
                "tool_morphology_summary",
                "tool_generate_report",
            ],
        }
        task = request.task or "morphology_summary"
        return task_to_tools.get(task, task_to_tools["morphology_summary"])
