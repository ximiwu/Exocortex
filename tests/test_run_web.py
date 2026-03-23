import os
import sys
import time

import pytest
from types import SimpleNamespace

import run_web


def test_production_requires_prebuilt_dist(tmp_path, monkeypatch):
    dist_file = tmp_path / "dist" / "index.html"
    dist_file.parent.mkdir(parents=True)
    monkeypatch.setattr(run_web, "WEB_DIST_INDEX", dist_file)

    with pytest.raises(RuntimeError) as excinfo:
        run_web.ensure_frontend_dist_available()

    assert run_web.PRODUCTION_DIST_ERROR in str(excinfo.value)


def _patch_web_paths(tmp_path, inputs, monkeypatch, dist_file):
    monkeypatch.setattr(run_web, "WEB_DIR", tmp_path)
    monkeypatch.setattr(run_web, "WEB_BUILD_INPUTS", inputs)
    monkeypatch.setattr(run_web, "WEB_DIST_INDEX", dist_file)


def test_frontend_build_required_when_sources_newer(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    dist_file = dist_dir / "index.html"
    dist_file.write_text("built")
    earlier = time.time() - 1000
    os.utime(dist_file, (earlier, earlier))

    src_dir = tmp_path / "src"
    public_dir = tmp_path / "public"
    src_dir.mkdir()
    public_dir.mkdir()
    (src_dir / "entry.ts").write_text("entry")
    (public_dir / "asset.txt").write_text("asset")

    now = time.time()
    os.utime(src_dir / "entry.ts", (now, now))
    os.utime(public_dir / "asset.txt", (now, now))

    inputs = []
    for name in ("index.html", "package.json", "package-lock.json", "vite.config.ts"):
        file = tmp_path / name
        file.write_text(name)
        os.utime(file, (now, now))
        inputs.append(file)

    _patch_web_paths(tmp_path, inputs, monkeypatch, dist_file)
    assert run_web.frontend_build_required()


def test_frontend_build_not_required_when_dist_newer(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    dist_file = dist_dir / "index.html"
    dist_file.write_text("built")
    future = time.time() + 100
    os.utime(dist_file, (future, future))

    src_dir = tmp_path / "src"
    public_dir = tmp_path / "public"
    src_dir.mkdir()
    public_dir.mkdir()
    (src_dir / "entry.ts").write_text("entry")
    (public_dir / "asset.txt").write_text("asset")

    old = future - 200
    os.utime(src_dir / "entry.ts", (old, old))
    os.utime(public_dir / "asset.txt", (old, old))

    inputs = []
    for name in ("index.html", "package.json", "package-lock.json", "vite.config.ts"):
        file = tmp_path / name
        file.write_text(name)
        os.utime(file, (old - 100, old - 100))
        inputs.append(file)

    _patch_web_paths(tmp_path, inputs, monkeypatch, dist_file)
    assert not run_web.frontend_build_required()


class _FakeEventHook:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


class _FakeWindow:
    def __init__(self):
        self.events = type(
            "Events",
            (),
            {
                "maximized": _FakeEventHook(),
                "restored": _FakeEventHook(),
                "before_show": _FakeEventHook(),
            },
        )()
        self.state = type("State", (), {"isMaximized": False})()
        self.minimize_called = 0
        self.maximize_called = 0
        self.restore_called = 0
        self.destroy_called = 0
        self.native = None

    def minimize(self):
        self.minimize_called += 1

    def maximize(self):
        self.maximize_called += 1

    def restore(self):
        self.restore_called += 1

    def destroy(self):
        self.destroy_called += 1


def test_open_in_desktop_shell_uses_frameless_custom_window(monkeypatch):
    window = _FakeWindow()
    captured = {}

    class FakeWebviewModule:
        @staticmethod
        def create_window(title, url, **kwargs):
            captured["title"] = title
            captured["url"] = url
            captured["kwargs"] = kwargs
            return window

        @staticmethod
        def start(**kwargs):
            captured["start_kwargs"] = kwargs

    monkeypatch.setitem(sys.modules, "webview", FakeWebviewModule)

    assert run_web.open_in_desktop_shell("http://localhost:9999", title="Exocortex", width=1400, height=900)
    assert captured["kwargs"]["frameless"] is True
    assert captured["kwargs"]["easy_drag"] is False
    assert captured["kwargs"]["maximized"] is False
    assert captured["kwargs"]["js_api"].getWindowState() == {"isMaximized": False}
    assert window.state.isMaximized is False

    captured["kwargs"]["js_api"].minimize()
    captured["kwargs"]["js_api"].toggleMaximize()
    captured["kwargs"]["js_api"].toggleMaximize()
    captured["kwargs"]["js_api"].close()

    assert window.minimize_called == 1
    assert window.restore_called == 1
    assert window.maximize_called == 1
    assert window.destroy_called == 1


class _FakeBounds:
    def __init__(self, x, y, width, height):
        self.X = x
        self.Y = y
        self.Width = width
        self.Height = height


class _FakeNativeForm:
    def __init__(self, *, working_area=None, bounds=None):
        self.WorkingArea = working_area or _FakeBounds(0, 0, 1024, 768)
        self.Bounds = bounds or _FakeBounds(128, 64, 800, 600)
        self.MaximizedBounds = None
        self.WindowState = None
        self.SetBoundsCalled = None

    def SetBounds(self, x, y, width, height, flag):
        self.SetBoundsCalled = (x, y, width, height, flag)
        self.Bounds = _FakeBounds(x, y, width, height)


class _FakeFormWindowState:
    Normal = "normal"
    Maximized = "max"


class _FakeBoundsSpecified:
    All = 99


def test_desktop_window_api_respects_workarea(monkeypatch):
    monkeypatch.setattr(run_web, "WinForms", SimpleNamespace(
        FormWindowState=_FakeFormWindowState,
        BoundsSpecified=_FakeBoundsSpecified,
        Screen=SimpleNamespace(FromControl=lambda native: SimpleNamespace(WorkingArea=native.WorkingArea)),
    ))
    window = _FakeWindow()
    window.native = _FakeNativeForm()
    api = run_web.DesktopWindowApi()
    api.bind(window)
    # simulate before_show event to trigger maximize path
    window.events.before_show.handlers[0]()
    assert window.state.isMaximized is True
    native = window.native
    assert native is not None
    assert native.WindowState == _FakeFormWindowState.Maximized
    assert native.MaximizedBounds == native.WorkingArea
    api.toggleMaximize()
    assert window.state.isMaximized is False
    assert window.restore_called == 1
    assert native.WindowState == _FakeFormWindowState.Maximized
    assert native.SetBoundsCalled is None


def test_desktop_window_api_supports_negative_monitor_coordinates(monkeypatch):
    monkeypatch.setattr(run_web, "WinForms", SimpleNamespace(
        FormWindowState=_FakeFormWindowState,
        BoundsSpecified=_FakeBoundsSpecified,
        Screen=SimpleNamespace(FromControl=lambda native: SimpleNamespace(WorkingArea=native.WorkingArea)),
    ))
    window = _FakeWindow()
    window.native = _FakeNativeForm(
        working_area=_FakeBounds(-1440, 0, 1440, 900),
        bounds=_FakeBounds(-1180, 48, 960, 720),
    )
    api = run_web.DesktopWindowApi()
    api.bind(window)

    window.events.before_show.handlers[0]()
    native = window.native
    assert native is not None
    assert native.MaximizedBounds == native.WorkingArea
    assert (native.MaximizedBounds.X, native.MaximizedBounds.Y) == (-1440, 0)

    api.toggleMaximize()

    assert window.restore_called == 1
    assert native.WindowState == _FakeFormWindowState.Maximized
    assert native.SetBoundsCalled is None


def test_main_stops_server_after_desktop_window_closes(monkeypatch):
    should_exit_states: list[bool] = []
    join_calls: list[float] = []

    class FakeThread:
        def __init__(self, target=None, name=None, daemon=None):
            self.target = target
            self.name = name
            self.daemon = daemon
            self._alive = False

        def start(self):
            self._alive = True

        def is_alive(self):
            return self._alive

        def join(self, timeout=None):
            join_calls.append(timeout)
            self._alive = False

    class FakeServer:
        def __init__(self, config):
            self.config = config
            self._should_exit = False

        def run(self):
            return None

        @property
        def should_exit(self):
            return self._should_exit

        @should_exit.setter
        def should_exit(self, value):
            self._should_exit = value
            should_exit_states.append(value)

    monkeypatch.setattr(
        run_web,
        "parse_args",
        lambda: SimpleNamespace(dev=False, browser=False, title="Exocortex", width=1440, height=960),
    )
    monkeypatch.setattr(run_web, "ensure_frontend_dist_available", lambda: None)
    monkeypatch.setattr(run_web, "find_free_port", lambda host=run_web.HOST: 8765)
    monkeypatch.setattr(run_web, "wait_for_healthcheck", lambda url: True)
    monkeypatch.setattr(run_web, "open_in_desktop_shell", lambda *args, **kwargs: True)
    monkeypatch.setattr(run_web, "open_in_system_browser", lambda *args, **kwargs: pytest.fail("browser mode should not be used"))
    monkeypatch.setattr(run_web.threading, "Thread", FakeThread)
    monkeypatch.setattr(run_web.uvicorn, "Config", lambda *args, **kwargs: SimpleNamespace(args=args, kwargs=kwargs))
    monkeypatch.setattr(run_web.uvicorn, "Server", FakeServer)

    assert run_web.main() == 0
    assert True in should_exit_states
    assert join_calls
