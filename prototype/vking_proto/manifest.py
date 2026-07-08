"""Run manifest and gate result schemas (§7)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    VACUOUS = "VACUOUS"
    N_A = "N/A"
    SKIP = "SKIP"


class GateResult(BaseModel):
    gate: str
    status: GateStatus
    message: str = ""
    backend: str | None = None


class ArtifactPaths(BaseModel):
    tb: str | None = None
    dut: str | None = None
    filelist: str | None = None
    waves: str | None = None
    log: str | None = None
    vvp: str | None = None
    compile_log: str | None = None
    manifest: str | None = None
    sim_log: str | None = None


class RunManifest(BaseModel):
    run_id: str
    timestamp: str
    module: str
    param_set: dict[str, Any] = Field(default_factory=dict)
    dialect_profile: str = "V2005-safe"
    backend: str = "iverilog"
    backend_version: str | None = None
    flags: list[str] = Field(default_factory=list)
    seed: int | None = None
    timescale: str | None = None
    gate_results: dict[str, GateResult] = Field(default_factory=dict)
    vacuity_report: list[dict[str, Any]] = Field(default_factory=list)
    waivers_applied: list[str] = Field(default_factory=list)
    artifact_paths: ArtifactPaths = Field(default_factory=ArtifactPaths)

    def to_json(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    def write_json(self, path: str) -> None:
        from pathlib import Path

        Path(path).write_text(self.to_json(), encoding="utf-8")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def artifact_urls(self, base: str = "/api/artifacts") -> dict[str, str]:
        from pathlib import Path

        rid = self.run_id
        urls: dict[str, str] = {}
        for key, path in self.artifact_paths.model_dump().items():
            if path:
                urls[key] = f"{base}/{rid}/{Path(path).name}"
        return urls
