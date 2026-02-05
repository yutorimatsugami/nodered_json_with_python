#!/usr/bin/env python3
"""
Patrol Service - パトロールロジック

役割:
- 混雑度に応じた自動巡回制御
- Guest検知時の自動接近
- UIイベントの処理
- タイマー制御
"""

import json
import math
import time
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

import paho.mqtt.client as mqtt

import config

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class CongestionLevel(Enum):
    UNKNOWN = "unknown"
    NORMAL = "normal"
    CROWDED = "crowded"


@dataclass
class TemiState:
    """Temiロボットの状態"""
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0
    status: str = "unknown"


@dataclass
class PatrolState:
    """パトロールの状態"""
    system_enabled: bool = False
    patrol_active: bool = False
    guest_handling: bool = False
    is_recording: bool = False
    current_index: int = 0
    prev_level: CongestionLevel = CongestionLevel.UNKNOWN
    idle_count: int = 0
    last_speech_time: float = 0.0
    last_move_time: float = 0.0
    waiting_for_arrival: bool = False
    arrival_timeout: float = 0.0


class PatrolService:
    """パトロールサービス"""
    
    def __init__(self):
        self.state = PatrolState()
        self.temi = TemiState()
        self.client: Optional[mqtt.Client] = None
        self._running = False
        self._timer_thread: Optional[threading.Thread] = None
        self._logs: list = []  # 管理者UI用ログ
        self._max_logs = 50    # ログ最大保持数
    
    # =========================================================================
    #  MQTT 接続
    # =========================================================================
    
    def connect(self):
        """MQTT ブローカーに接続"""
        self.client = mqtt.Client()
        # Aedes（認証なし）の場合はコメントアウト
        # self.client.username_pw_set(config.MQTT_USER, config.MQTT_PASSWORD)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
        logger.info(f"Connecting to MQTT broker: {config.MQTT_BROKER}:{config.MQTT_PORT}")
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT 接続時のコールバック"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            # トピック購読
            client.subscribe(config.TOPIC_UI_EVENT)
            client.subscribe(config.TOPIC_YOLO_DATA)
            client.subscribe(config.TOPIC_TEMI_STATUS)
            logger.info("Subscribed to topics")
        else:
            logger.error(f"Connection failed with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """MQTT メッセージ受信時のコールバック"""
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            
            if topic == config.TOPIC_UI_EVENT:
                self._handle_ui_event(payload)
            elif topic == config.TOPIC_YOLO_DATA:
                self._handle_yolo_data(payload)
            elif topic == config.TOPIC_TEMI_STATUS:
                self._handle_temi_status(payload)
                
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    # =========================================================================
    #  UI イベント処理
    # =========================================================================
    
    def _handle_ui_event(self, payload: dict):
        """UIイベントを処理"""
        mode = payload.get("mode", "")
        
        if mode == "init":
            # メニュー画面表示 → パトロール中断
            self.state.patrol_active = False
            self.state.guest_handling = True
            self.state.idle_count = 0
            self.state.is_recording = False
            self._send_temi_command({"command": "stop"})
            logger.info("UI操作: パトロール中断・案内モード")
            self._add_log("UI操作: パトロール中断・案内モード")
            
        elif mode == "reset":
            # リセット → パトロール復帰待機
            self.state.guest_handling = False
            self.state.patrol_active = False
            self.state.prev_level = CongestionLevel.UNKNOWN
            self.state.idle_count = 0
            self.state.is_recording = False
            self.state.waiting_for_arrival = False
            logger.info("UIリセット: パトロール復帰待ち")
            self._add_log("UIリセット: パトロール復帰待ち")
            
        elif mode == "start":
            # パトロール開始
            self.state.system_enabled = True
            self.state.guest_handling = False
            self.state.waiting_for_arrival = False
            self.state.idle_count = 0
            self.state.prev_level = CongestionLevel.UNKNOWN
            self.state.current_index = 0
            logger.info("システム開始: 自動判定有効")
            self._add_log("システム開始: 自動判定有効")
            
        elif mode == "stop":
            # パトロール停止（その場で停止）
            self.state.system_enabled = False
            self.state.patrol_active = False
            self.state.guest_handling = False
            self.state.idle_count = 0
            self._send_temi_command({"command": "stop"})
            logger.info("システム停止: その場で待機")
            self._add_log("システム停止: その場で待機")
            
        elif mode == "goHome":
            # ホームへ帰還（手動操作）
            self.state.system_enabled = False
            self.state.patrol_active = False
            self.state.guest_handling = False
            self.state.idle_count = 0
            self._goto_location("home base")
            logger.info("ホームへ帰還")
            self._add_log("ホームへ帰還")
            
        elif mode == "startRecording":
            self.state.is_recording = True
            self.state.idle_count = 0
            logger.info("録音開始")
            
        elif mode == "stopRecording":
            self.state.is_recording = False
            self.state.idle_count = 0
            logger.info("録音停止")
            
        else:
            # その他のUI操作 → タイマーリセットのみ
            self.state.idle_count = 0
    
    # =========================================================================
    #  YOLO データ処理
    # =========================================================================
    
    def _handle_yolo_data(self, payload: dict):
        """YOLOセンサーデータを処理"""
        if not self.state.system_enabled:
            return
        
        # 混雑度を取得
        level_str = payload.get("congestion_level", "").lower()
        try:
            current_level = CongestionLevel(level_str)
        except ValueError:
            current_level = CongestionLevel.UNKNOWN
        
        # Crowded時はGuest検知をスキップ
        if current_level != CongestionLevel.CROWDED:
            self._handle_guest_detection(payload)
        
        # 混雑度判定
        self._handle_congestion_level(current_level)
    
    def _handle_guest_detection(self, payload: dict):
        """Guest検知処理"""
        stay_alerts = payload.get("stay_alerts", [])
        
        if not stay_alerts or self.state.guest_handling:
            return
        
        alert = stay_alerts[0]
        world_coords = alert.get("world_coords", [])
        
        if len(world_coords) != 2:
            return
        
        gx, gy = world_coords[0], world_coords[1]
        target = self._calc_guest_approach_target(gx, gy)
        
        if target:
            logger.info(f"Guest検知: 接近開始 ({target[0]:.2f}, {target[1]:.2f})")
            self.state.patrol_active = False
            self.state.guest_handling = True
            self.state.idle_count = 0
            self._goto_position(target[0], target[1], target[2])
    
    def _handle_congestion_level(self, current_level: CongestionLevel):
        """混雑度に応じた処理"""
        if current_level == CongestionLevel.UNKNOWN:
            return
        
        if current_level == self.state.prev_level:
            return
        
        self.state.prev_level = current_level
        
        if current_level == CongestionLevel.NORMAL:
            if self.state.guest_handling:
                return
            logger.info("判定: normal (パトロール開始)")
            self.state.patrol_active = True
            self.state.idle_count = 0
            self._goto_patrol_point()
            
        elif current_level == CongestionLevel.CROWDED:
            logger.info("判定: crowded (その場で待機)")
            self._add_log("判定: crowded (その場で待機)")
            self.state.patrol_active = False
            self._send_temi_command({"command": "stop"})
    
    # =========================================================================
    #  Temi 状態更新
    # =========================================================================
    
    def _handle_temi_status(self, payload: dict):
        """Temi状態を更新"""
        where = payload.get("where", {})
        what = payload.get("what", {})
        
        if "x" in where:
            self.temi.x = float(where["x"])
        if "y" in where:
            self.temi.y = float(where["y"])
        if "heading" in where:
            self.temi.heading = float(where["heading"])
        
        self.temi.status = what.get("status", "unknown")
        
        # 移動完了チェック
        status_lower = self.temi.status.lower()
        if self.state.waiting_for_arrival:
            if status_lower == "complete":
                logger.info("移動完了を確認 (status=complete)")
                self.state.waiting_for_arrival = False
                self.state.idle_count = 0
            elif status_lower == "abort" or status_lower == "stop":
                logger.info(f"移動中断を確認 (status={status_lower})")
                self.state.waiting_for_arrival = False
                self.state.idle_count = 0
    
    # =========================================================================
    #  タイマー処理
    # =========================================================================
    
    def _start_timer(self):
        """1秒タイマーを開始"""
        self._running = True
        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()
    
    def _timer_loop(self):
        """タイマーループ"""
        while self._running:
            time.sleep(1)
            self._on_timer_tick()
    
    def _on_timer_tick(self):
        """1秒ごとの処理"""
        # Idle判定 (コマンド送信直後 5秒間は無視)
        is_moving_wait = (time.time() - self.state.last_move_time) < 5.0
        is_temi_idle = self.temi.status.lower() in ["idle", "complete", "stop", "abort", "unknown", ""]
        
        is_idle = is_temi_idle and (not is_moving_wait)
        
        # 音声案内
        now = time.time()
        if now - self.state.last_speech_time >= config.SPEECH_INTERVAL:
            self._speak_announcement()
            self.state.last_speech_time = now
        
        if is_idle and not self.state.is_recording:
            self.state.idle_count += 1
            self._broadcast_status()
            
            # Guest タイムアウト
            if self.state.guest_handling and self.state.idle_count >= config.GUEST_TIMEOUT:
                logger.info(f"Guestタイムアウト ({config.GUEST_TIMEOUT}s): パトロール復帰")
                self._add_log(f"Guestタイムアウト: パトロール復帰")
                self.state.guest_handling = False
                self.state.prev_level = CongestionLevel.UNKNOWN
                self.state.idle_count = 0
                self._send_ui_control({"mode": "reset"})
            
            # パトロール次ポイント
            if (self.state.patrol_active and 
                not self.state.guest_handling and 
                not self.state.waiting_for_arrival and
                self.state.idle_count >= config.PATROL_IDLE_TIME):
                self.state.idle_count = 0
                self.state.current_index = (self.state.current_index + 1) % len(config.PATROL_POINTS)
                logger.info(f"パトロール: 次の地点へ移動 (index={self.state.current_index})")
                self._add_log("パトロール: 次の地点へ移動")
                self._goto_patrol_point()
        
        # 到着待ちタイムアウト監視 (15秒)
        if self.state.waiting_for_arrival:
            if time.time() > self.state.arrival_timeout:
                logger.warning(f"移動タイムアウト: 到着扱いとして続行 (Current Status: {self.temi.status})")
                self.state.waiting_for_arrival = False
                self.state.idle_count = config.PATROL_IDLE_TIME
        else:
            if self.state.idle_count > 0:
                self.state.idle_count = 0
                self._broadcast_status()
    
    # =========================================================================
    #  コマンド送信
    # =========================================================================
    
    def _send_temi_command(self, command: dict):
        """Temiにコマンドを送信"""
        if self.client:
            self.client.publish(config.TOPIC_TEMI_COMMAND, json.dumps(command))
    
    def _goto_location(self, location: str):
        """指定ロケーションへ移動"""
        self._send_temi_command({
            "command": "gotoLocation",
            "position": {"location": location}
        })
        self.state.last_move_time = time.time()
        self.state.waiting_for_arrival = True
        self.state.arrival_timeout = time.time() + 20.0
    
    def _goto_position(self, x: float, y: float, yaw: float):
        """指定座標へ移動"""
        self._send_temi_command({
            "command": "goToPosition",
            "position": {"x": x, "y": y, "degrees": round(yaw), "speed": 0.2}
        })
        self.state.last_move_time = time.time()
        self.state.waiting_for_arrival = True
        self.state.arrival_timeout = time.time() + 20.0
    
    def _goto_patrol_point(self):
        """現在のパトロールポイントへ移動"""
        location = config.PATROL_POINTS[self.state.current_index]
        self._goto_location(location)
    
    def _speak_announcement(self):
        """音声案内を再生"""
        # ゲスト対応中（案内パネル操作中）は発話しない
        if self.state.guest_handling:
            return
        
        if self.state.patrol_active:
            text = "現在、案内ロボットが移動中です。案内パネルをタッチするとロボットが案内いたします。"
        else:
            text = "お困りですか？案内パネルをタッチするとロボットが案内いたします。"
        
        self._send_temi_command({"command": "speak", "content": text})
    
    def _send_ui_control(self, payload: dict):
        """UIに制御コマンドを送信"""
        if self.client:
            self.client.publish(config.TOPIC_UI_CONTROL, json.dumps(payload))
    
    def _add_log(self, message: str):
        """管理者UI用ログを追加"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self._logs.append(log_entry)
        if len(self._logs) > self._max_logs:
            self._logs.pop(0)
    
    def _broadcast_status(self):
        """管理者UIにステータスを送信"""
        status = {
            "summary": f"Tick: {self.state.idle_count}s",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "logs": self._logs[-20:],  # 最新20件
            "debug": {
                "idleCount": self.state.idle_count,
                "guestHandling": self.state.guest_handling,
                "patrolActive": self.state.patrol_active,
                "temiStatus": self.temi.status,
                "systemEnabled": self.state.system_enabled,
                "angle": {
                    "target": 0,
                    "current": round(self.temi.heading)
                }
            }
        }
        if self.client:
            self.client.publish(config.TOPIC_ADMIN_INFO, json.dumps(status))
    
    # =========================================================================
    #  座標計算
    # =========================================================================
    
    def _calc_guest_approach_target(self, gx: float, gy: float) -> Optional[Tuple[float, float, float]]:
        """Guestへの接近目標座標を計算"""
        tx, ty = self.temi.x, self.temi.y
        
        dx = tx - gx
        dy = ty - gy
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist < 0.1:
            return (gx + config.GUEST_APPROACH_OFFSET, gy, 180.0)
        
        # オフセット位置を計算
        target_x = gx + (dx / dist) * config.GUEST_APPROACH_OFFSET
        target_y = gy + (dy / dist) * config.GUEST_APPROACH_OFFSET
        
        # Guestを向く角度を計算
        look_dx = gx - target_x
        look_dy = gy - target_y
        angle_rad = math.atan2(look_dy, look_dx)
        target_yaw = math.degrees(angle_rad) + 180
        
        # 正規化
        while target_yaw > 180:
            target_yaw -= 360
        while target_yaw < -180:
            target_yaw += 360
        
        return (target_x, target_y, target_yaw)
    
    # =========================================================================
    #  メイン
    # =========================================================================
    
    def run(self):
        """サービスを開始"""
        self.connect()
        self._start_timer()
        
        logger.info("Patrol Service started. Press Ctrl+C to stop.")
        
        try:
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Stopping...")
            self._running = False
            self.client.disconnect()


if __name__ == "__main__":
    service = PatrolService()
    service.run()
