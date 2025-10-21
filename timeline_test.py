from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QApplication

from timeline_widget import TimelineWindow


class TimelineDemo(QObject):
    """演示如何与时间轴进行双向交互的简易示例。"""

    def __init__(self) -> None:
        super().__init__()
        self.window = TimelineWindow(load_demo=False)

        bridge = self.window.bridge
        bridge.pageReady.connect(self.on_page_ready)
        bridge.eventReceived.connect(self.on_event_received)
        bridge.logMessage.connect(self.on_log_message)
        bridge.projectStateChanged.connect(self.on_project_state)

        self.window.show()

    @Slot()
    def on_page_ready(self) -> None:
        """页面准备好之后，从 Python 端注入轨道与剪辑。"""
        print("时间轴已加载，开始注入数据...")

        self.window.bridge.add_track(
            {
                "id": "L10",
                "number": 10,
                "label": "演示",
                "color": "#dcdfe3",
                "lock": False,
            }
        )

        self.window.bridge.add_clip(
            {
                "id": "clip-demo",
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

        self.window.bridge.add_clip(
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

        self.window.bridge.resize_timeline(100)
        self.window.bridge.move_playhead(50)
        self.window.bridge.set_timeline_frame_rate(50)
        self.window.bridge.get_timeline_info()

        self.window.bridge.request_project_state()
        self.window.bridge.play_playhead()
        print("已添加轨道与片段，可以尝试在时间轴中拖动该片段。")

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


def main() -> int:
    app = QApplication(sys.argv)
    demo = TimelineDemo()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
