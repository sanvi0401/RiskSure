"""Keep Windows browser startup and diagnostic output safe and repeatable."""
import subprocess
from types import SimpleNamespace

import pytest

from scripts import verify_browser


def test_browser_startup_does_not_inherit_capture_pipes(monkeypatch):
    calls = []
    monkeypatch.setattr(verify_browser.shutil, "which", lambda name: "npx")

    def run(command, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(returncode=0, stdout=None)

    monkeypatch.setattr(verify_browser.subprocess, "run", run)
    assert verify_browser.browser(["open", "https://example.invalid"], capture_output=False) == ""
    assert calls[0]["stdout"] == subprocess.DEVNULL
    assert calls[0]["stderr"] == subprocess.DEVNULL
    assert "capture_output" not in calls[0]


def test_browser_timeout_does_not_expose_arguments(monkeypatch):
    monkeypatch.setattr(verify_browser.shutil, "which", lambda name: "npx")

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(verify_browser.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="Browser action timed out: fill") as caught:
        verify_browser.browser(["fill", "input", "private-unit-test-value"])
    assert "private-unit-test-value" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_multiline_input_uses_native_enter_keys(monkeypatch):
    calls = []
    monkeypatch.setattr(verify_browser, "browser", lambda arguments: calls.append(arguments))
    verify_browser.fill_multiline("textarea", "First paragraph\nSecond paragraph")
    assert calls == [["fill", "textarea", "First paragraph"], ["press", "Control+End"],
                     ["press", "Enter"], ["type", "textarea", "Second paragraph"]]
    assert all("\n" not in argument for call in calls for argument in call)
