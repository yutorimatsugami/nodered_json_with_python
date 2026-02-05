#!/usr/bin/env python3
"""
YOLO Topic Test - YOLOセンサーデータをシミュレートして送信

使用方法:
    python yolo_topic_test.py
"""

import paho.mqtt.client as mqtt
import json
import time
import random

# --- 設定 ---
BROKER_ADDRESS = "192.168.11.7"
PORT = 1883
TOPIC = "station/sensor/data"
INTERVAL = 2.5  # 送信間隔（秒）


def send_continuously():
    client = mqtt.Client()
    # Aedes（認証なし）のため認証設定は不要
    # client.username_pw_set("test", "4701")

    try:
        client.connect(BROKER_ADDRESS, PORT)
        print(f"送信を開始します... (Topic: {TOPIC})")
        print("Ctrl+C で終了")

        while True:
            # ランダムに状況を変える
            total_count = random.randint(0, 10)
            congestion = "crowded" if total_count > 5 else "normal"
            
            # 案内が必要な人のリスト（normal時のみ生成）
            stay_alerts = []
            if congestion == "normal" and random.random() > 0.7:
                stay_alerts.append({
                    "track_id": random.randint(1, 100),
                    "stay_duration": round(random.uniform(10.0, 60.0), 1),
                    "feet_coords": [random.randint(100, 800), random.randint(100, 500)],
                    "world_coords": [round(random.uniform(1.0, 5.0), 1), 
                                     round(random.uniform(1.0, 5.0), 1)],
                    "state": "Stopped"
                })

            data = {
                "timestamp": int(time.time()),
                "total_count": total_count,
                "congestion_level": congestion,
                "robot_active": congestion != "crowded",
                "stay_alerts": stay_alerts
            }

            json_payload = json.dumps(data, ensure_ascii=False)
            client.publish(TOPIC, json_payload)
            
            status = "🔴 crowded" if congestion == "crowded" else "🟢 normal"
            alert_info = f" [Guest検知: {len(stay_alerts)}人]" if stay_alerts else ""
            print(f"[{time.strftime('%H:%M:%S')}] {status} - 人数: {total_count}{alert_info}")
            
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print("\nプログラムを終了します。")
    finally:
        client.disconnect()


if __name__ == "__main__":
    send_continuously()
