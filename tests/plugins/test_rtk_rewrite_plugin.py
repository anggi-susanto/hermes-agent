"""Tests for the bundled RTK terminal command rewrite plugin."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace


PLUGIN_PATH = Path(__file__).resolve().parents[2] / "plugins" / "rtk-rewrite" / "__init__.py"


def _load_plugin():
    spec = importlib.util.spec_from_file_location("hermes_test_rtk_rewrite", PLUGIN_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DummyContext:
    def __init__(self):
        self.hooks = []

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


def test_register_skips_when_rtk_missing(monkeypatch, caplog):
    plugin = _load_plugin()
    monkeypatch.setattr(plugin.shutil, "which", lambda name: None)

    ctx = DummyContext()
    plugin.register(ctx)

    assert ctx.hooks == []
    assert "rtk binary not found" in caplog.text


def test_register_adds_pre_tool_call_when_rtk_available(monkeypatch):
    plugin = _load_plugin()
    monkeypatch.setattr(plugin.shutil, "which", lambda name: "/usr/bin/rtk")

    ctx = DummyContext()
    plugin.register(ctx)

    assert len(ctx.hooks) == 1
    assert ctx.hooks[0][0] == "pre_tool_call"


def test_pre_tool_call_rewrites_terminal_command(monkeypatch):
    plugin = _load_plugin()
    monkeypatch.setattr(plugin, "_run_rtk_rewrite", lambda command: "rtk git status\n")

    args = {"command": "git status", "timeout": 30}
    plugin._pre_tool_call(tool_name="terminal", args=args)

    assert args["command"] == "rtk git status"
    assert args["timeout"] == 30


def test_pre_tool_call_ignores_non_terminal_tools(monkeypatch):
    plugin = _load_plugin()
    calls = []
    monkeypatch.setattr(plugin, "_run_rtk_rewrite", lambda command: calls.append(command) or "rtk git status")

    args = {"command": "git status"}
    plugin._pre_tool_call(tool_name="read_file", args=args)

    assert args["command"] == "git status"
    assert calls == []


def test_pre_tool_call_fails_open_when_rewrite_has_no_replacement(monkeypatch):
    plugin = _load_plugin()
    monkeypatch.setattr(plugin, "_run_rtk_rewrite", lambda command: None)

    args = {"command": "git status"}
    plugin._pre_tool_call(tool_name="terminal", args=args)

    assert args["command"] == "git status"


def test_run_rtk_rewrite_accepts_changed_command(monkeypatch):
    plugin = _load_plugin()

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=3, stdout="rtk git status\n", stderr="")

    monkeypatch.setattr(plugin.subprocess, "run", fake_run)

    assert plugin._run_rtk_rewrite("git status") == "rtk git status\n"


def test_run_rtk_rewrite_expected_passthrough_returns_none(monkeypatch):
    plugin = _load_plugin()

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="git status\n", stderr="")

    monkeypatch.setattr(plugin.subprocess, "run", fake_run)

    assert plugin._run_rtk_rewrite("git status") is None


def test_run_rtk_rewrite_timeout_fails_open(monkeypatch, caplog):
    plugin = _load_plugin()

    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="rtk rewrite", timeout=2)

    monkeypatch.setattr(plugin.subprocess, "run", fake_run)

    assert plugin._run_rtk_rewrite("git status") is None
    assert "rtk rewrite timed out" in caplog.text
