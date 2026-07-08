# Node-RED + Python ハイブリッドアーキテクチャ

案内ロボットシステムのハイブリッド構成。UIはNode-RED、ロジックはPythonで実装。

## ディレクトリ構成

```
nodered_json_with_python/
├── README.md                    # このファイル
├── manifest.json                # UIテンプレート注入マッピング（build_flow.py用）
├── flows/                       # Node-REDフロー（ビルド成果物含む）
│   ├── mqtt_broker_flow.json    # ★ MQTTブローカー (Aedes)
│   ├── robot_ui_flow.json       # エンドユーザー向けUI（手編集禁止・ビルド成果物）
│   └── admin_ui_flow.json       # 管理者ダッシュボード
├── src/                         # robot_ui_flow.json から外部化したUIテンプレート
│   ├── ui/
│   │   └── main_template.html   # UIテンプレート本体（HTML+CSS+JS）
│   ├── i18n.js                  # 多言語データ（scope.i18n オブジェクトリテラル）
│   └── flows/
│       └── robot_ui_flow.skeleton.json  # プレースホルダー入りフロー骨格
├── tools/                       # フロービルドツール
│   ├── extract_flow.py          # flows/robot_ui_flow.json → src/ へ抽出
│   └── build_flow.py            # src/ → flows/robot_ui_flow.json を再生成
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

## 🧩 UIテンプレートのビルドフロー

`robot_ui_flow.json` の `node_ui_template_main`（画面表示ノード）は19,000文字超のHTML+CSS+JSを1つの文字列フィールドに丸ごと保持しており、フローJSONを直接編集するのは差分レビューも困難でした。パトロールロジックを `python/patrol_service.py` に外部化したのと同じ考え方で、UIテンプレートも `src/` 配下のソースファイルに外部化しています。

### 編集ルール

- **UIテンプレートの編集は `src/ui/main_template.html`（多言語文言は `src/i18n.js`）で行う。**
- **`flows/robot_ui_flow.json` は手編集禁止（ビルド成果物）。** 直接編集すると次回ビルド時に上書きされます。

### ビルド（src/ → flows/robot_ui_flow.json）

`src/` を編集したら、以下でフローJSONを再生成します。

```bash
python3 tools/build_flow.py
```

`--check` を付けると、実際にはファイルを書き換えずに現在の `flows/robot_ui_flow.json` との差分の有無だけを確認できます（CIや編集前チェックに利用）。

```bash
python3 tools/build_flow.py --check
```

### 逆抽出（flows/robot_ui_flow.json → src/）

Node-REDエディタ側でテンプレートを直接編集してしまった場合は、以下で `src/` 側に再抽出して同期を取り直します。

```bash
python3 tools/extract_flow.py
```

抽出・ビルドのマッピングは `manifest.json` に記録されており（対象ノードID・フィールド名・分割元ファイル）、`build_flow.py` と `extract_flow.py` はこれを共有します。

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

## 🛠️ 更新履歴 (2026/02/05)

### パトロール動作の改善
1. **到着待機ロジックの導入**:
   - Temiへの移動コマンド送信後、ステータスが `complete`（完了）になるまで次のコマンド送信を待機するように変更しました。
   - これにより、移動中に次の目的地への指示が重複して送信される問題を解消しました。

2. **タイムアウト処理の追加**:
   - Temiからの到着通知が届かない環境（ネットワーク不安定など）を考慮し、移動指示から **20秒** 経過しても通知がない場合は、自動的に到着済みとみなして次の動作へ進むタイムアウト処理を追加しました。
   - タイムアウト時間は `patrol_service.py` 内で調整可能です。
