# PySide6 时间轴封装说明

本项目把 `timeline/` 目录中的 HTML/JavaScript 时间轴界面（源自 OpenShot）嵌入到 PySide6 的 `QWebEngineView` 中，并通过 `QtWebChannel` 实现双向通信。Python 端既可以主动添加/修改/删除轨道与剪辑，也能实时接收前端交互事件。

## 环境要求

- Python 3.9 及以上
- PySide6（示例基于 `PySide6==6.7.0`，需包含 QtWebEngine 模块）

安装依赖：

```bash
pip install -r pyproject.toml
```

仅安装 PySide6：

```bash
pip install PySide6==6.7.0
```

## 目录结构

- `main.py`：定义 `TimelineWindow` 与 `TimelineBridge`，封装 WebEngine 页面和 Qt ↔ JS 调用。
- `timeline/index.html`：时间轴前端入口，包含 AngularJS + jQuery 的 UI 逻辑。
- `timeline/js/mixin_webengine.js`：Qt WebChannel Mixin，负责在前端创建 `timeline` 代理对象。
- `timeline/js/pyside_bridge.js`：前端暴露给 Python 的 API（`window.timelineApi`）。
- `timeline/media/css/main.css`：样式文件，已调整为浅色主题（白色背景、银色轨道、剪辑可自定义颜色）。
- `test.py`：示例脚本，展示常见调用流程与事件监听。

## TimelineBridge 信号与方法

### 信号

- `pageReady()`：Angular 初始化完毕，可以安全推送数据。
- `logMessage(level, message)`：前端日志输出。
- `eventReceived(method, args)`：前端调用了未在 Python 侧实现的 `timeline.*` 方法（如拖动剪辑后的 `update_clip_data`）。
- `projectStateChanged(state)`：调用 `request_project_state()` 或前端主动同步项目时触发，`state` 为完整 JSON。

### 方法一览

| 方法                                                         | 参数                                                         | 说明                                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| `add_track(track: dict)`                                     | `track` 含 `id`、`number`、`label`、`color` 等               | 添加或更新轨道（若 `id`/`number` 已存在则覆盖）。            |
| `remove_track(track_identifier, *, keep_clips=False, allow_shrink=False)` | 轨道 `id` 或 `number`                                        | 删除轨道。默认同时删除其剪辑；`keep_clips=True` 可保留剪辑；`allow_shrink=True` 时允许删除后收缩时间轴。 |
| `add_clip(clip: dict)`                                       | `clip` 含 `id`、`layer`、`position`、`duration`、`color` 等  | 添加或更新剪辑，缺省字段自动补齐。                           |
| `remove_clip(clip_id: str)`                                  | 剪辑 `id`                                                    | 删除指定剪辑。                                               |
| `update_clip(clip_id: str, **patch)`                         | 任意字段                                                     | 局部更新剪辑（标题、时间、颜色等）。                         |
| `move_clip(clip_id: str, layer=None, position=None, **options)` | `layer` 目标轨道，`position` 目标时间；`options` 可含 `start`/`duration`/`end` | 迁移剪辑并可同步调整时长。                                   |
| `set_clip_color(clip_id: str, color: str, text_color: str \| None = None)` | 背景色与文字色                                               | 设置剪辑颜色。                                               |
| `set_project_state(state: dict)`                             | 完整项目 JSON                                                | 用给定状态覆盖整个时间轴。                                   |
| `get_timeline_info()`                                        | -                                                            | 读取当前时间线的所有信息，包含 `fps`、`duration`、`tracks` 以及完整的剪辑列表。 |
| `set_timeline_frame_rate(fps)`                               | 接受 `float` 帧率、`(num, den)` 元组或 `{"num": , "den": }` 字典 | 更新时间线帧率，触发前端刷新剪辑和轨道。                     |
| `request_project_state()`                                    | –                                                            | 请求前端回传项目 JSON（触发 `projectStateChanged`）。        |
| `resize_timeline(duration: float, *, allow_shrink: bool = True)` | 目标时长（秒）                                               | 设置时间轴总长度；若缩短后小于最后一个剪辑，会自动对齐到最后剪辑。`allow_shrink=False` 时仅延长、不缩短。 |
| `move_playhead(seconds: float)`                              | 时间（秒）                                                   | 移动播放头位置。                                             |
| `set_playhead_playing(playing: bool, *, start_at: float \| None = None)` | `playing=True/False` 控制播放状态，`start_at` 可选起始时间   | 启动或停止播放头自动播放，可选地在播放前定位到指定时间。     |
| `play_playhead(*, start_at: float \| None = None)`           | 可选起始时间                                                 | `set_playhead_playing(True, …)` 的便捷封装。                 |
| `pause_playhead()`                                           | -                                                            | 暂停播放头动画。                                             |
| `toggle_playhead()`                                          | -                                                            | 播放/暂停切换，适合绑定热键。                                |

> 说明：`add_clip`、`move_clip` 等操作只会在新剪辑超出当前末尾时延长时间轴，不会自动缩短。如需缩短请调用 `resize_timeline`。

## 前端事件与数据结构

大多数用户操作都会触发 `timeline.*` 方法。例如拖动剪辑结束时会执行：

```javascript
timeline.update_clip_data(JSON.stringify(item_data), true, true, false, transactionId);
```

该调用会被 `TimelineBridge.invoke()` 捕获，从而触发 Python 侧的 `eventReceived`。在槽函数中解析参数即可获得剪辑的新位置。示例脚本 `test.py` 展示了如何监听 `update_clip_data` 并打印拖动结果。

常用数据模型示例：

- **轨道 (Track)**

```json
{
  "id": "L1",
  "number": 1,
  "label": "视频轨 1",
  "color": "#d9d9d9",
  "lock": false
}
```

- **剪辑 (Clip)**

```json
{
  "id": "clip-demo",
  "layer": 1,
  "position": 2.0,
  "start": 0.0,
  "duration": 5.0,
  "end": 5.0,
  "title": "示例片段",
  "image": "./media/images/thumbnail.png",
  "color": "#5b8def",
  "text_color": "#ffffff",
  "reader": {"has_video": true, "has_audio": false}
}
```

`timelineApi` 会自动补齐 `duration`、`end`、`reader.fps` 等缺省字段，保证时间轴行为一致。

### 修改时间线帧率

Python 可以直接调整时间线帧率：

```python
 timeline_window.bridge.set_timeline_frame_rate(29.97)
 # 也可以传入分数形式
 timeline_window.bridge.set_timeline_frame_rate((24000, 1001))
```

前端会自动刷新各轨道和剪辑的渲染状态。

## 前端交互增强

- `Ctrl + 鼠标滚轮` 以当前光标位置为中心缩放时间轴，快速查看细节或全局。
- `Shift + 鼠标滚轮` 快速横向平移轨道区域。
- Python 侧可调用 `TimelineBridge.play_playhead()` / `pause_playhead()` 控制播放头自动播放，也可通过 `set_playhead_playing(..., start_at=秒数)` 预先定位后再播放。

## 示例脚本（`timeline_test.py`）

运行：

```bash
python timeline_test.py
```

流程：

1. 创建 `TimelineWindow` 并等待页面初始化。

2. 添加自定义轨道与剪辑，设置颜色。

3. 移动播放头到剪辑位置。

4. 监听 `update_clip_data`，拖动后打印轨道与时间。

5. 调用 `request_project_state()`，在 `projectStateChanged` 中输出当前轨道与剪辑数量。

## 主题与外观

- 背景：浅灰/白色。
- 轨道：默认银色，可通过 `layer.color` 调整。
- 剪辑：默认蓝色，可通过 `clip.color` 与 `clip.text_color` 自定义。

如需进一步个性化，可直接修改 `timeline/media/css/main.css`，或扩展 `timelineApi` 注入主题参数。

## 调试建议

- 需要前端调试时，可启用 DevTools：`QWebEngineSettings::defaultSettings()->setAttribute(QWebEngineSettings::DeveloperExtrasEnabled, True)`，随后在窗口中按 `Ctrl+Shift+I`。
- 纯浏览器打开 `timeline/index.html` 可进行离线调试（无 Qt 通道，但带 demo 数据）。

## 许可证

`timeline/` 中的资源来自 OpenShot（GPLv3）。其余 Python 封装代码遵循仓库默认许可证。若用于商业或闭源项目，请确认兼容性。
