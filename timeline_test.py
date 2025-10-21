from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QApplication

from timeline_widget import TimelineWidget, ensure_resources_initialized
from PySide6.QtWidgets import QMainWindow
from PySide6.QtGui import QAction


class TimelineDemo(QMainWindow):
    """演示如何与时间轴进行双向交互的简易示例。"""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("PySide6 Timeline Wrapper")
        self.resize(1280, 720)

        self.timeline = TimelineWidget(load_demo=False)
        self.setCentralWidget(self.timeline)

        bridge = self.timeline.bridge
        bridge.pageReady.connect(self.on_page_ready)
        bridge.eventReceived.connect(self.on_event_received)
        bridge.logMessage.connect(self.on_log_message)
        bridge.projectStateChanged.connect(self.on_project_state)
        self._init_menu_bar()

    @Slot()
    def on_page_ready(self) -> None:
        """页面准备好之后，从 Python 端注入轨道与剪辑。"""
        print("时间轴已加载，开始注入数据...")

        self.timeline.bridge.add_track(
            {
                "id": "L10",
                "number": 10,
                "label": "演示",
                "color": "#dcdfe3",
                "lock": False,
            }
        )

        self.timeline.bridge.add_clip(
            {
                "id": "clip3-demo",
                "layer": 0,
                "title": "演示片段",
                "position": 1.5,
                "start": 0.0,
                "duration": 15,
                "image": "./media/images/thumbnail.png",
                "reader": {"has_video": False, "has_audio": False},
                "color": "#00f375c3",
                "text_color": "#1f1f1f",
            }
        )

        self.timeline.bridge.add_clip(
            {
                "id": "clip2-demo",
                "layer": 10,
                "title": "演示片段",
                "position": 1.5,
                "start": 0.0,
                "duration": 13,
                "image": "./media/images/thumbnail.png",
                "reader": {"has_video": False, "has_audio": False},
                "color": "#146139c3",
                "text_color": "#b55d5d",
            }
        )

        self.timeline.bridge.resize_timeline(100)
        self.timeline.bridge.move_playhead(24)
        self.timeline.bridge.set_timeline_frame_rate(30)

    @Slot(str, list)
    def on_event_received(self, method: str, args: List[Any]) -> None:
        """
        处理来自 JavaScript 端的事件。
        我们重点关注 `update_clip_data`，它在拖动剪辑后触发。
        """
        if method != "update_clip_data" or not args:
            return

        clip_payload = args[0]
        try:
            clip_data = json.loads(clip_payload)
        except (TypeError, json.JSONDecodeError):
            return

        clip_id = clip_data.get("id", "unknown")
        layer = clip_data.get("layer")
        position = clip_data.get("position")
        if position is not None:
            print(f"剪辑 {clip_id} 当前位于轨道 {layer}，时间 {position:.2f} 秒")
        else:
            print(f"剪辑 {clip_id} 位置信息未知")

    @Slot(dict)
    def on_project_state(self, state: Dict[str, Any]) -> None:
        """收到完整时间轴状态快照后打印概要信息。"""
        track_count = len(state.get("layers", []))
        clip_count = len(state.get("clips", []))
        print(f"[状态快照] 轨道: {track_count} 条，剪辑: {clip_count} 个")

    @Slot(str, str)
    def on_log_message(self, level: str, message: str) -> None:
        """打印前端发来的日志，便于调试。"""
        print(f"[前端 {level}] {message}")

    def test_func_1(self) -> None:
        print("Test action 1 clicked")
        self.timeline.bridge.play_playhead()
        print(self.timeline.bridge.get_timeline_info())

    def test_func_2(self) -> None:
        print("Test action 2 clicked")
        self.timeline.bridge.pause_playhead()
        self.timeline.bridge.request_project_state()

    def _init_menu_bar(self) -> None:
        """Add a simple test menu for manual actions."""
        menu_bar = self.menuBar()
        test_menu = menu_bar.addMenu("Tests")

        test_action_1 = QAction("Test Action 1", self)
        test_action_1.triggered.connect(self.test_func_1)

        test_action_2 = QAction("Test Action 2", self)
        test_action_2.triggered.connect(self.test_func_2)

        test_menu.addAction(test_action_1)
        test_menu.addAction(test_action_2)


def main() -> int:
    app = QApplication(sys.argv)
    ensure_resources_initialized()
    window = TimelineDemo()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
