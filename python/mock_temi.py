#!/usr/bin/env python3
"""
Mock Temi - Temiロボットの動作をシミュレート

使用方法:
    python mock_temi.py
"""

import paho.mqtt.client as mqtt
import json
import time
import random
import threading

# --- 設定 ---
BROKER_ADDRESS = "192.168.11.7"
PORT = 1883
TEMI_ID = "temi01"
TOPIC_COMMAND = f"request/{TEMI_ID}"
TOPIC_STATUS = f"info/{TEMI_ID}"

# 現在の状態
state = {
    "x": 0.0,
    "y": 0.0,
    "heading": 0.0,
    "status": "idle",
    "location": "home base"
}


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connected to MQTT broker")
        client.subscribe(TOPIC_COMMAND)
        client.subscribe("request")  # 一斉コマンド
        print(f"📡 Subscribed to: {TOPIC_COMMAND}, request")
    else:
        print(f"❌ Connection failed: {rc}")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        command = payload.get("command", "")
        
        print(f"\n📥 受信: {command}")
        
        if command == "gotoLocation":
            location = payload.get("position", {}).get("location", "unknown")
            handle_goto_location(client, location)
            
        elif command == "goToPosition":
            pos = payload.get("position", {})
            handle_goto_position(client, pos)
            
        elif command == "speak":
            text = payload.get("content", "")
            handle_speak(client, text)
            
        elif command == "stop":
            handle_stop(client)
            
        else:
            print(f"⚠️ 未知のコマンド: {command}")
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def handle_goto_location(client, location):
    global state
    print(f"🚶 移動開始: {location}")
    state["status"] = "moving"
    state["location"] = location
    publish_status(client)
    
    # 移動シミュレーション
    time.sleep(random.uniform(2.0, 4.0))
    
    state["status"] = "idle"
    print(f"✅ 到着: {location}")
    publish_status(client)


def handle_goto_position(client, pos):
    global state
    x = pos.get("x", 0)
    y = pos.get("y", 0)
    degrees = pos.get("degrees", 0)
    
    print(f"🚶 座標移動: ({x}, {y}) 角度: {degrees}°")
    state["status"] = "moving"
    publish_status(client)
    
    # 移動シミュレーション
    time.sleep(random.uniform(2.0, 4.0))
    
    state["x"] = x
    state["y"] = y
    state["heading"] = degrees
    state["status"] = "idle"
    print(f"✅ 到着: ({x}, {y})")
    publish_status(client)


def handle_speak(client, text):
    global state
    print(f"🗣️ 発話: {text[:30]}...")
    state["status"] = "speaking"
    publish_status(client)
    
    # 発話シミュレーション
    time.sleep(2.0)
    
    state["status"] = "idle"
    publish_status(client)


def handle_stop(client):
    global state
    print("🛑 停止")
    state["status"] = "idle"
    publish_status(client)


def publish_status(client):
    status = {
        "where": {
            "x": state["x"],
            "y": state["y"],
            "heading": state["heading"]
        },
        "what": {
            "status": state["status"],
            "location": state["location"]
        }
    }
    client.publish(TOPIC_STATUS, json.dumps(status))
    print(f"📤 ステータス送信: {state['status']}")


def status_publisher(client):
    """定期的にステータスを送信"""
    while True:
        time.sleep(5)
        publish_status(client)


def main():
    client = mqtt.Client()
    # Aedes（認証なし）のため認証設定は不要
    # client.username_pw_set("test", "4701")
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    print(f"🤖 Mock Temi ({TEMI_ID}) を起動します...")
    print(f"   Broker: {BROKER_ADDRESS}:{PORT}")
    
    try:
        client.connect(BROKER_ADDRESS, PORT)
        
        # 定期ステータス送信スレッド
        status_thread = threading.Thread(target=status_publisher, args=(client,), daemon=True)
        status_thread.start()
        
        print("Ctrl+C で終了")
        client.loop_forever()
        
    except KeyboardInterrupt:
        print("\n🛑 プログラムを終了します。")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
