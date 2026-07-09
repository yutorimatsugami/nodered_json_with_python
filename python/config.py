"""
MQTT & システム設定
"""

# MQTT Broker (aedes on Node-RED)
MQTT_BROKER = "192.168.11.2"  # Node-RED内蔵aedesブローカー
MQTT_PORT = 1883
MQTT_USER = ""  # aedesデフォルトは認証なし
MQTT_PASSWORD = ""

# MQTT Topics
TOPIC_UI_EVENT = "internal/ui_event"           # UI → Python
TOPIC_UI_CONTROL = "internal/ui_control"       # Python → UI
TOPIC_ADMIN_INFO = "internal/admin/info"       # Python → Admin UI
TOPIC_YOLO_DATA = "station/sensor/data"        # YOLO → Python
TOPIC_TEMI_STATUS = "info/temi01"              # Temi → Python
TOPIC_TEMI_COMMAND = "request/temi01"          # Python → Temi

# Patrol Points
PATROL_POINTS = [
    "kaisatu",
    "jihannki",
    "gomibako",
    "elevator 1 2",
    "home 1 2",
    "toire",
    "home 3 4",
    "conbini",
    "elevator 3 4"
]

# Timeouts (seconds)
GUEST_TIMEOUT = 20          # Guest対応のタイムアウト
PATROL_IDLE_TIME = 5        # 次のポイントへ移動するまでの待機時間
SPEECH_INTERVAL = 10        # 音声案内の間隔

# Guest Detection
GUEST_APPROACH_OFFSET = 0.8  # ゲストへの接近距離 (m)
