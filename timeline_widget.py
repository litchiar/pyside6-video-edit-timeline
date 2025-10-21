import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PySide6.QtCore import QObject, QUrl, Signal, Slot, QEventLoop, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow


ROOT_DIR = Path(__file__).resolve().parent
TIMELINE_HTML = ROOT_DIR / "timeline" / "index.html"


class TimelineBridge(QObject):
    """Qt WebChannel bridge exposed to the embedded timeline page."""

    logMessage = Signal(str, str)
    pageReady = Signal()
    eventReceived = Signal(str, list)
    projectStateChanged = Signal(dict)

    def __init__(self, view: QWebEngineView) -> None:
        super().__init__()
        self._view = view

    # --- Slots callable from JavaScript ---------------------------------
    @Slot(str, str)
    def qt_log(self, level: str, message: str) -> None:
        """Receive log messages from the JS timeline and forward them."""
        self.logMessage.emit(level, message)

    @Slot()
    def page_ready(self) -> bool:
        """Called by the JS mixin when Angular has finished booting."""
        self.pageReady.emit()
        return True

    @Slot(str, "QVariantList", result="QVariant")
    def invoke(self, method: str, args: List[Any]) -> Any:
        """
        Generic fall-back for timeline methods that don't have dedicated slots.
        Emits the method name and arguments so Python can react as needed.
        """
        py_args = self._convert_variant(args)
        if method == "project_state":
            state_payload: Any = py_args[0] if py_args else {}
            if isinstance(state_payload, str):
                try:
                    state = json.loads(state_payload)
                except json.JSONDecodeError:
                    state = {}
            elif isinstance(state_payload, dict):
                state = state_payload
            else:
                state = {}
            self.projectStateChanged.emit(state)
            self.eventReceived.emit(method, [state])
            return state

        self.eventReceived.emit(method, py_args)
        return None

    # --- Python helpers to call into JavaScript --------------------------
    def add_clip(self, clip: dict[str, Any]) -> None:
        """Add or update a clip on the timeline via the helper API."""
        self._run_js(f"window.timelineApi?.addClip({json.dumps(clip)})")

    def add_track(self, track: dict[str, Any]) -> None:
        """Add or update a track/layer definition on the timeline."""
        self._run_js(f"window.timelineApi?.addTrack({json.dumps(track)})")

    def remove_track(
        self,
        track_identifier: Any,
        *,
        keep_clips: bool = False,
        allow_shrink: bool = False,
    ) -> None:
        """Remove a track. Clips are deleted unless keep_clips=True."""
        identifier_js = json.dumps(track_identifier)
        options_js = json.dumps({"keepClips": keep_clips, "allowShrink": allow_shrink})
        self._run_js(f"window.timelineApi?.removeTrack({identifier_js}, {options_js})")

    def remove_clip(self, clip_id: str) -> None:
        """Remove a clip from the timeline."""
        self._run_js(f"window.timelineApi?.removeClip({json.dumps(clip_id)})")

    def update_clip(self, clip_id: str, **patch: Any) -> None:
        """Merge updates into an existing clip."""
        self._run_js(
            f"window.timelineApi?.updateClip({json.dumps(clip_id)}, {json.dumps(patch)})"
        )

    def move_clip(
        self,
        clip_id: str,
        layer: Optional[Any] = None,
        position: Optional[float] = None,
        **options: Any,
    ) -> None:
        """Move a clip to a new layer and/or position on the timeline."""
        layer_js = "null" if layer is None else json.dumps(layer)
        position_js = "null" if position is None else json.dumps(position)
        options_js = json.dumps(options or {})
        self._run_js(
            f"window.timelineApi?.moveClip({json.dumps(clip_id)}, {layer_js}, {position_js}, {options_js})"
        )

    def set_playhead_playing(
        self, playing: bool, *, start_at: Optional[float] = None
    ) -> None:
        """
        Control automatic playhead animation on the JavaScript timeline.
        When `start_at` is provided, the playhead jumps there before playing.
        """
        options: Dict[str, Any] = {}
        if start_at is not None:
            options["startAt"] = float(start_at)
        options_js = "undefined" if not options else json.dumps(options)
        js_playing = "true" if playing else "false"
        self._run_js(
            f"window.timelineApi?.setPlayheadPlaying({js_playing}, {options_js})"
        )

    def play_playhead(self, *, start_at: Optional[float] = None) -> None:
        """Start playhead playback, optionally from a specific position."""
        self.set_playhead_playing(True, start_at=start_at)

    def pause_playhead(self) -> None:
        """Pause any active playhead playback animation."""
        self.set_playhead_playing(False)

    def toggle_playhead(self) -> None:
        """Toggle between playing and paused playhead states."""
        self._run_js("window.timelineApi?.togglePlayhead()")

    def set_clip_color(
        self, clip_id: str, color: str, text_color: Optional[str] = None
    ) -> None:
        """Update the visual color of a clip (and optional text color)."""
        text_color_js = "null" if text_color is None else json.dumps(text_color)
        self._run_js(
            f"window.timelineApi?.setClipColor({json.dumps(clip_id)}, {json.dumps(color)}, {text_color_js})"
        )

    def set_project_state(self, project_state: dict[str, Any]) -> None:
        """Replace the full project state on the JS side."""
        self._run_js(
            f"window.timelineApi?.setProjectState({json.dumps(project_state)})"
        )

    def get_timeline_info(self) -> dict[str, Any]:
        """
        Fetch the current state of the timeline including fps, duration, tracks and clips.
        Returns an empty dictionary if the timeline is not ready yet.
        """
        info = self._evaluate_js("window.timelineApi?.collectTimelineInfo?.()", None)
        return info if isinstance(info, dict) else {}

    def set_timeline_frame_rate(
        self,
        fps: Union[float, Tuple[int, int], dict[str, Any]],
    ) -> None:
        """
        Update the timeline playback frame rate.
        Accepts a float (frames per second), a (num, den) tuple, or a dictionary with num/den.
        """
        payload: Any
        if isinstance(fps, tuple):
            num, den = fps
            payload = {
                "num": int(num),
                "den": int(den) if int(den) != 0 else 1,
            }
        elif isinstance(fps, dict):
            payload = {
                "num": int(fps.get("num", 0) or 0),
                "den": int(fps.get("den", 1) or 1),
            }
            if payload["den"] == 0:
                payload["den"] = 1
        else:
            payload = float(fps)

        self._run_js(f"window.timelineApi?.setFrameRate({json.dumps(payload)})")

    def resize_timeline(self, duration: float, *, allow_shrink: bool = True) -> None:
        """Resize the overall timeline length (can't go shorter than the last clip)."""
        options = {"allowShrink": allow_shrink}
        self._run_js(
            f"window.timelineApi?.resizeTimeline({float(duration)}, {json.dumps(options)})"
        )

    def request_project_state(self) -> None:
        """Ask the JS timeline to emit the current project JSON via projectStateChanged."""
        self._run_js("window.timelineApi?.emitProjectState()")

    def move_playhead(self, seconds: float) -> None:
        """Move the playhead to a specific timestamp."""
        self._run_js(f"window.timelineApi?.movePlayhead({float(seconds)})")

    # --- Internal utilities ---------------------------------------------
    def _run_js(self, script: str) -> None:
        """Execute JavaScript on the current page."""
        if self._view.page():
            self._view.page().runJavaScript(script)

    def _evaluate_js(self, script: str, default: Any) -> Any:
        """
        Execute JavaScript and wait for the return value.
        A short timeout prevents hangs if the page is not ready.
        """
        page = self._view.page()
        if not page:
            return default

        loop = QEventLoop()
        result: Dict[str, Any] = {"value": default}

        def on_timeout() -> None:
            if loop.isRunning():
                loop.quit()

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(on_timeout)
        timer.start(2000)

        def callback(value: Any) -> None:
            result["value"] = value
            if loop.isRunning():
                loop.quit()

        page.runJavaScript(script, callback)
        loop.exec()
        timer.stop()
        return self._convert_variant(result["value"])

    @staticmethod
    def _convert_variant(value: Any) -> Any:
        """Recursively convert Qt's QVariant containers into Python values."""
        if isinstance(value, list):
            return [TimelineBridge._convert_variant(v) for v in value]
        if isinstance(value, dict):
            return {
                key: TimelineBridge._convert_variant(val) for key, val in value.items()
            }
        return value


class TimelineWindow(QMainWindow):
    """Main window hosting the timeline in a QWebEngineView."""

    def __init__(self, *, load_demo: bool = True) -> None:
        super().__init__()
        self.setWindowTitle("PySide6 Timeline Wrapper")
        self.resize(1280, 720)
        self._load_demo = load_demo

        self.view = QWebEngineView(self)
        # self.view.settings().setAttribute(
        #     QWebEngineSettings.LocalContentCanAccessFileUrls, True
        # )
        self.setCentralWidget(self.view)

        self.channel = QWebChannel(self.view.page())
        self.bridge = TimelineBridge(self.view)
        self.channel.registerObject("timeline", self.bridge)
        self.view.page().setWebChannel(self.channel)

        self.bridge.pageReady.connect(self._on_page_ready)
        self.bridge.logMessage.connect(self._on_log_message)
        self.bridge.eventReceived.connect(self._on_event_received)
        self.bridge.projectStateChanged.connect(self._on_project_state)

        if not TIMELINE_HTML.exists():
            raise FileNotFoundError(f"Timeline entry point not found: {TIMELINE_HTML}")
        self.view.load(QUrl.fromLocalFile(str(TIMELINE_HTML)))

    # --- Callbacks ------------------------------------------------------
    def _on_page_ready(self) -> None:
        """
        Populates the timeline with example data once Angular reports ready.
        Adjust this to drive the timeline with real project data.
        """
        if not self._load_demo:
            return

        self.bridge.add_track(
            {
                "id": "L1",
                "number": 1,
                "label": "Demo Track",
                "y": 0,
                "lock": False,
                "color": "#d9d9d9",
            }
        )

        demo_clip = {
            "id": "clip-demo",
            "layer": 1,
            "image": "./media/images/thumbnail.png",
            "locked": False,
            "duration": 5.0,
            "start": 0.0,
            "end": 5.0,
            "position": 2.0,
            "title": "Demo Clip",
            "effects": [],
            "images": {"start": 1, "end": 1},
            "show_audio": False,
            "alpha": {"Points": []},
            "location_x": {"Points": []},
            "location_y": {"Points": []},
            "scale_x": {"Points": []},
            "scale_y": {"Points": []},
            "rotation": {"Points": []},
            "time": {"Points": []},
            "volume": {"Points": []},
            "reader": {"has_video": True, "has_audio": False},
            "color": "#5b8def",
            "text_color": "#ffffff",
        }
        self.bridge.add_clip(demo_clip)
        self.bridge.move_playhead(2.0)

    @staticmethod
    def _on_project_state(state: Dict[str, Any]) -> None:
        track_count = len(state.get("layers", []))
        clip_count = len(state.get("clips", []))
        print(f"[Timeline State] tracks={track_count} clips={clip_count}")

    @staticmethod
    def _on_log_message(level: str, message: str) -> None:
        print(f"[Timeline][{level}] {message}")

    @staticmethod
    def _on_event_received(method: str, args: list[Any]) -> None:
        """
        Debug hook for events coming from the HTML timeline.
        Replace with real signal/slot wiring in production.
        """
        print(f"[Timeline Event] {method} -> {args}")


def main() -> int:
    """Qt application entry point."""
    app = QApplication(sys.argv)
    # Ensure WebEngine resources are initialized in headless contexts
    if not QGuiApplication.primaryScreen():
        QGuiApplication.setQuitOnLastWindowClosed(True)

    window = TimelineWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
