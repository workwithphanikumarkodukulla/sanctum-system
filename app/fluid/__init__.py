"""Sanctum Fluid Architecture package.

Layers:
  Bottom — Local Model Layer: isolated model pool, auto-profiled capabilities
  Middle — Workspace Layer: isolated per-workspace context
  Top    — Agent/UI Layer: request routing, tool execution

No model knows about another model's data.
No workspace knows about another workspace's data.
"""
from app.fluid.model_registry import ModelRegistry
from app.fluid.model_profiler import ModelProfiler
from app.fluid.workspace_registry import WorkspaceRegistry
from app.fluid.router import FluidRouter

__all__ = ["ModelRegistry", "ModelProfiler", "WorkspaceRegistry", "FluidRouter"]
