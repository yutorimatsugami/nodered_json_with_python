# Node-RED + Python ハイブリッドアーキテクチャ

案内ロボットシステムのハイブリッド構成。UIはNode-RED、ロジックはPythonで実装。

## ディレクトリ構成

```
nodered_json_with_python/
├── README.md                    # このファイル
├── flows/                       # Node-REDフロー
│   ├── mqtt_broker_flow.json    # ★ MQTTブローカー (Aedes)
│   ├── robot_ui_flow.json       # エンドユーザー向けUI
│   └── admin_ui_flow.json       # 管理者ダッシュボード
├── python/                      # Pythonサービス
│   ├── patrol_service.py        # パトロールロジック
│   ├── config.py                # 設定
│   ├── run.sh                   # 起動スクリプト
│   ├── requirements.txt         # 依存関係
│   ├── mock_temi.py             # ★ Temiシミュレーター
│   └── yolo_topic_test.py       # ★ YOLOデータシミュレーター
└── docs/
    └── mqtt_interface.md        # MQTTトピック仕様
```

## 役割分担

### Node-RED
- **MQTTブローカー** (Aedes) ← 外部Mosquitto不要！
- 画面表示（広告、メニュー、チャット、リモート通話）
- UIモード切り替え
- 管理者ダッシュボード表示

### Python
- パトロールロジック（状態管理）
- タイマー制御
- Guest検知・接近計算
- Temiへのコマンド送信

---

## 🚀 起動方法

### 起動順序（重要）

```
1. Node-RED     ← MQTTブローカーが先に起動
   ↓
2. mock_temi.py ← Temiシミュレーター（本番ではTemi実機）
   ↓
3. run.sh       ← Patrol Service
   ↓
4. yolo_topic_test.py ← YOLOシミュレーター（本番ではYOLO）
```

### 1. Node-RED 起動 & フローインポート

```bash
node-red
```

1. Node-REDエディタを開く（https://192.168.11.7:1880）
2. メニュー → インポート → **すべてのフローを順番にインポート**:
   - `flows/mqtt_broker_flow.json` ← **最初に！**
   - `flows/robot_ui_flow.json`
   - `flows/admin_ui_flow.json`
3. **デプロイ**をクリック

> ⚠️ `mqtt_broker_flow.json` をインポートしてデプロイすると、Node-RED内でMQTTブローカー（ポート1883）が起動します。

### 2. Temi シミュレーター起動（開発時のみ）

```bash
cd python
python mock_temi.py
```

### 3. Python サービス起動

```bash
cd python
./run.sh
```

### 4. YOLO シミュレーター起動（開発時のみ）

```bash
cd python
python yolo_topic_test.py
```

---

## 🎮 管理者コンソール

https://192.168.11.7:1880/ui の「管理者コンソール」タブ

### 操作パネル

| ボタン | 動作 |
|--------|------|
| **Start Patrol** 🟢 | システム開始、パトロール有効化 |
| **Stop Patrol** 🔴 | その場で停止 |
| **System Reset** 🟡 | UIリセット |
| **Go Home** 🔵 | ホームへ帰還 |

### システム動作

| 状況 | 動作 |
|------|------|
| **normal検知** | パトロール再開 |
| **crowded検知** | その場で停止（ホームに帰らない） |
| **ゲスト検知** | 接近して案内開始 |
| **ゲスト対応中にcrowded** | 停止するがゲスト対応継続 |
| **ゲスト対応中** | 音声案内なし |

---

## 📡 MQTT 設定

### 接続情報

| 項目 | 値 |
|------|------|
| ブローカー | `192.168.11.7` または `localhost` |
| ポート | `1883` |
| 認証 | **なし** (Aedes) |
| 暗号化 | なし |

> ⚠️ 以前のMosquitto（Docker）は使用しません。Node-RED内のAedesがブローカーです。

### MQTT トピック

| トピック | 方向 | 用途 |
|----------|------|------|
| `internal/ui_event` | UI → Python | UI操作イベント |
| `internal/ui_control` | Python → UI | UI制御コマンド |
| `internal/admin/info` | Python → Admin | 管理者ステータス |
| `station/sensor/data` | YOLO → Python | 混雑度・Guest座標 |
| `info/temi01` | Temi → Python | ロボット状態 |
| `request/temi01` | Python → Temi | 移動コマンド |

---

## 🌐 ネットワーク設定

### IPアドレスの確認

```bash
# Linux
ip addr show | grep "inet "
```

例: `192.168.11.7`

### 設定変更が必要なファイル

| ファイル | 変更箇所 |
|----------|----------|
| `python/config.py` | `MQTT_BROKER = "192.168.11.7"` |
| `flows/*.json` | mqtt-broker の `broker` を変更 |

### アクセス方法

```
https://192.168.11.7:1880/ui
```

---

## 🔒 HTTPS化（マイク機能を使う場合 必須）

**Web Audio API（音声入力）を使うにはHTTPS化が必須です。**

### 現在の設定

証明書ファイル: `/home/yutori/Documents/cert/`
- `key.pem`
- `cert.pem`

settings.js に以下が設定済み:

```javascript
https: {
  key: require("fs").readFileSync('/home/yutori/Documents/cert/key.pem'),
  cert: require("fs").readFileSync('/home/yutori/Documents/cert/cert.pem')
},
```

> ⚠️ 自己署名証明書のため、ブラウザで「安全ではありません」警告が出ます。

---

## 🧪 テストスクリプト

### mock_temi.py

Temiロボットの動作をシミュレート。

```bash
python mock_temi.py
```

**機能:**
- `gotoLocation` - ロケーション移動
- `goToPosition` - 座標移動
- `speak` - 発話
- `stop` - 停止
- 5秒ごとにステータス送信

### yolo_topic_test.py

YOLOセンサーデータをシミュレート。

```bash
python yolo_topic_test.py
```

**機能:**
- 2.5秒ごとにデータ送信
- ランダムに normal / crowded を切り替え
- ランダムにGuest検知を発生

---

## 📋 環境構築チェックリスト

- [ ] Node-RED をインストール (`npm install -g node-red`)
- [ ] node-red-contrib-aedes をインストール (`cd ~/.node-red && npm install node-red-contrib-aedes`)
- [ ] node-red-dashboard をインストール (`cd ~/.node-red && npm install node-red-dashboard`)
- [ ] Python 3.x をインストール
- [ ] 全フローをインポート・デプロイ
- [ ] Python Patrol Service を起動
- [ ] HTTPS 化（設定済み）

---

## 🎯 動作確認

1. Node-RED ダッシュボード (`https://192.168.11.7:1880/ui`) にアクセス
2. 広告画面が表示されることを確認
3. 画面タッチでメニュー画面に遷移
4. Python側のログに `UI操作: パトロール中断・案内モード` が表示されれば成功
5. 管理者コンソールでシステムログが表示されることを確認
