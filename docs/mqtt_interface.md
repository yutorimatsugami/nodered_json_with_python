# MQTT インターフェース仕様

## 概要

Node-RED（UI）と Python（ロジック）間の通信仕様。

## トピック一覧

| トピック | 方向 | 送信元 | 受信先 | 用途 |
|----------|------|--------|--------|------|
| `internal/ui_event` | → | Node-RED | Python | UI操作イベント |
| `internal/ui_control` | ← | Python | Node-RED | UI制御コマンド |
| `internal/admin/info` | ← | Python | Admin UI | ステータス情報 |
| `station/sensor/data` | → | YOLO | Python | 混雑度・Guest座標 |
| `info/temi01` | → | Temi | Python | ロボット状態 |
| `request/temi01` | ← | Python | Temi | 移動コマンド |

---

## internal/ui_event

**方向**: Node-RED → Python

UIからのイベントを通知。

### Payload

```json
{
  "mode": "init" | "reset" | "start" | "stop" | "startRecording" | "stopRecording" | "api_req" | ...
}
```

| mode | 説明 |
|------|------|
| `init` | メニュー画面表示（パトロール中断） |
| `reset` | 広告画面に戻る |
| `start` | パトロール開始 |
| `stop` | パトロール停止 |
| `startRecording` | 音声録音開始 |
| `stopRecording` | 音声録音終了 |
| その他 | タイマーリセットのみ |

---

## internal/ui_control

**方向**: Python → Node-RED

UIへの制御コマンド。

### Payload

```json
{
  "mode": "reset"
}
```

| mode | 説明 |
|------|------|
| `reset` | 広告画面に戻す |

---

## internal/admin/info

**方向**: Python → Admin UI

管理者画面へのステータス送信。

### Payload

```json
{
  "summary": "Tick: 5s",
  "timestamp": "2026-02-03T23:30:00",
  "debug": {
    "idleCount": 5,
    "guestHandling": false,
    "patrolActive": true,
    "temiStatus": "idle",
    "systemEnabled": true
  }
}
```

---

## station/sensor/data

**方向**: YOLO → Python

カメラ解析データ。

### Payload

```json
{
  "congestion_level": "normal" | "crowded",
  "stay_alerts": [
    {
      "world_coords": [1.5, 2.3]
    }
  ]
}
```

---

## info/temi01

**方向**: Temi → Python

ロボット状態。

### Payload

```json
{
  "where": {
    "x": 1.5,
    "y": 2.3,
    "heading": 0.5
  },
  "what": {
    "status": "idle" | "going" | "complete" | ...
  }
}
```

---

## request/temi01

**方向**: Python → Temi

ロボットへのコマンド。

### Payload

```json
// 移動（ロケーション名）
{
  "command": "gotoLocation",
  "position": { "location": "home base" }
}

// 移動（座標）
{
  "command": "goToPosition",
  "position": { "x": 1.5, "y": 2.3, "degrees": 90, "speed": 0.2 }
}

// 停止
{
  "command": "stop"
}

// 発話
{
  "command": "speak",
  "content": "こんにちは"
}
```
