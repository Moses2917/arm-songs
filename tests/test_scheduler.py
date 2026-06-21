"""
Tests for `hymns.tasks` and the `run_scheduler` management command that
replaced django-q2's qcluster.
"""
import threading
import time
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command

from hymns import tasks

pytestmark = pytest.mark.django_db


# --- hymns.tasks.scheduled_import --------------------------------------

def test_scheduled_import_returns_stats(tmp_path, settings, monkeypatch):
    # Point DATA_DIR at an empty dir so import_json short-circuits cleanly
    settings.DATA_DIR = str(tmp_path)
    stats = tasks.scheduled_import()
    assert stats == {
        "new_meta": 0, "old_meta": 0, "lyrics": 0,
        "themes_linked": 0, "services": 0, "service_links": 0,
    }


def test_scheduled_import_passes_data_dir_from_settings(tmp_path, settings):
    settings.DATA_DIR = str(tmp_path)
    with mock.patch("hymns.tasks.import_json", return_value={"ok": True}) as m:
        result = tasks.scheduled_import()
    m.assert_called_once_with(str(tmp_path))
    assert result == {"ok": True}


def test_scheduled_import_raises_and_logs_on_failure(settings, caplog):
    with mock.patch("hymns.tasks.import_json", side_effect=RuntimeError("boom")):
        with caplog.at_level("ERROR", logger="hymns.tasks"):
            with pytest.raises(RuntimeError, match="boom"):
                tasks.scheduled_import()
    assert any("scheduled_import failed" in r.message for r in caplog.records)


# --- run_scheduler command: --once -------------------------------------

def test_run_scheduler_once_invokes_scheduled_import(tmp_path, settings):
    settings.DATA_DIR = str(tmp_path)
    out = StringIO()
    err = StringIO()
    call_command("run_scheduler", "--once", stdout=out, stderr=err)
    assert "Running scheduled_import once." in out.getvalue()
    assert "scheduled_import ok:" in out.getvalue()


def test_run_scheduler_once_swallows_task_exception(tmp_path, settings):
    settings.DATA_DIR = str(tmp_path)
    out = StringIO()
    err = StringIO()
    # NOTE: patch where the name is looked up (the command module), not where
    # it's defined — `from hymns.tasks import scheduled_import` rebound it.
    with mock.patch(
        "hymns.management.commands.run_scheduler.scheduled_import",
        side_effect=RuntimeError("nope"),
    ):
        # must NOT raise — the command logs and continues
        call_command("run_scheduler", "--once", stdout=out, stderr=err)
    assert "scheduled_import failed" in err.getvalue()


# --- run_scheduler command: the threaded loop ---------------------------

def test_loop_runs_task_then_stops_when_event_set():
    from hymns.management.commands.run_scheduler import Command

    cmd = Command(stdout=StringIO(), stderr=StringIO())
    stop = threading.Event()
    calls = []

    def fake_run_once():
        calls.append(time.monotonic())
        # after 3 invocations, signal stop (from inside the worker thread)
        if len(calls) >= 3:
            stop.set()

    # Patch _run_once and shorten the interval wait by setting stop early.
    with mock.patch.object(cmd, "_run_once", side_effect=fake_run_once):
        with mock.patch.object(stop, "wait", lambda secs: None):
            cmd._loop(interval=0, stop=stop)

    assert len(calls) == 3
    assert stop.is_set()


def test_run_once_emits_success_and_closes_connections(tmp_path, settings):
    from django.db import close_old_connections
    from hymns.management.commands.run_scheduler import Command

    settings.DATA_DIR = str(tmp_path)
    cmd = Command(stdout=StringIO(), stderr=StringIO())
    with mock.patch("hymns.management.commands.run_scheduler.close_old_connections") as c:
        cmd._run_once()
    c.assert_called_once()
    assert "scheduled_import ok:" in cmd.stdout.getvalue()


def test_run_once_logs_exception_and_still_closes_connections():
    from hymns.management.commands.run_scheduler import Command

    cmd = Command(stdout=StringIO(), stderr=StringIO())
    with mock.patch(
        "hymns.management.commands.run_scheduler.scheduled_import",
        side_effect=RuntimeError("boom"),
    ):
        with mock.patch("hymns.management.commands.run_scheduler.close_old_connections") as c:
            cmd._run_once()
    c.assert_called_once()
    assert "scheduled_import failed" in cmd.stderr.getvalue()


# --- Signal handling: main thread registers SIGINT/SIGTERM --------------

def _patch_handle_environment(monkeypatch, loop_fn=None):
    """Neutralize the parts of handle() that touch real threads/signals.

    Returns a dict that collects the (signum -> handler) registrations so a
    test can invoke them. `loop_fn` replaces the worker loop if provided.
    """
    installed = {}

    def fake_signal(signum, handler):
        installed[signum] = handler

    monkeypatch.setattr(
        "hymns.management.commands.run_scheduler.signal.signal", fake_signal
    )
    if loop_fn is not None:
        monkeypatch.setattr(
            "hymns.management.commands.run_scheduler.Command._loop", loop_fn
        )
    return installed


def test_handle_registers_sigint_and_sigterm(monkeypatch):
    from hymns.management.commands.run_scheduler import Command

    installed = _patch_handle_environment(
        monkeypatch, loop_fn=lambda self, interval, stop: stop.set()
    )
    cmd = Command(stdout=StringIO(), stderr=StringIO())
    cmd.handle(minutes=1, once=False)

    import signal as sig_mod
    assert sig_mod.SIGINT in installed
    assert sig_mod.SIGTERM in installed
    assert callable(installed[sig_mod.SIGINT])
    assert callable(installed[sig_mod.SIGTERM])


def test_registered_signal_handler_sets_stop_event(monkeypatch):
    """End-to-end (mocked): the handler captured during handle() must, when
    invoked, set the stop event so the worker loop exits."""
    from hymns.management.commands.run_scheduler import Command

    seen_events = []

    def capturing_loop(self, interval, stop):
        # Record the event then block until something sets it (or short timeout)
        seen_events.append(stop)
        stop.wait(0.5)

    installed = _patch_handle_environment(monkeypatch, loop_fn=capturing_loop)

    cmd = Command(stdout=StringIO(), stderr=StringIO())
    import threading as _t

    t = _t.Thread(target=cmd.handle, kwargs={"minutes": 1, "once": False}, daemon=True)
    t.start()

    # wait for handle() to have registered the handlers
    deadline = time.monotonic() + 1.0
    while sig_int_not_yet_registered(installed) and time.monotonic() < deadline:
        time.sleep(0.005)

    import signal as sig_mod
    assert sig_mod.SIGINT in installed, "handle() did not register SIGINT"
    # invoke the handler as the kernel would
    installed[sig_mod.SIGTERM](sig_mod.SIGTERM, None)
    t.join(timeout=1.0)

    assert not t.is_alive(), "handle() should return after the handler sets stop"
    assert seen_events, "worker loop should have run"
    assert seen_events[0].is_set(), "the handler must set the stop event"


def sig_int_not_yet_registered(installed):
    import signal as sig_mod
    return sig_mod.SIGINT not in installed


# --- Command arguments -------------------------------------------------

def test_run_scheduler_accepts_minutes_argument():
    from hymns.management.commands.run_scheduler import Command

    parser_cmd = Command()
    parser = __import__("argparse").ArgumentParser()
    parser_cmd.add_arguments(parser)
    args = parser.parse_args(["--minutes", "5", "--once"])
    assert args.minutes == 5
    assert args.once is True


def test_run_scheduler_default_minutes_is_30():
    from hymns.management.commands.run_scheduler import Command

    parser_cmd = Command()
    parser = __import__("argparse").ArgumentParser()
    parser_cmd.add_arguments(parser)
    args = parser.parse_args([])
    assert args.minutes == 30
    assert args.once is False
