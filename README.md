# aiwolf-nlp-agent-llm (bmd チーム)

人狼知能コンテスト（自然言語部門）向けLLMエージェントです。
**デフォルトは9人村。** 5人村への切り替えも可能です。

## 前提条件

| ツール | バージョン | 備考 |
|--------|-----------|------|
| Python | 3.11以上 | |
| [uv](https://docs.astral.sh/uv/) | 最新版 | パッケージ管理 |
| LLM API | いずれか1つ | Google Gemini / OpenAI / Ollama |

---

## セットアップ

```bash
git clone <このリポジトリのURL>
cd aiwolf

# 依存関係のインストール
uv sync

# APIキーの設定
cp config/.env.example config/.env
# config/.env を編集して使用するAPIキーを記入
```

---

## 実行方法

### ① サーバーバイナリのダウンロード

macOS (Apple Silicon):
```bash
curl -L https://github.com/aiwolfdial/aiwolf-nlp-server/releases/latest/download/aiwolf-nlp-server-darwin-arm64 \
  -o server/aiwolf-nlp-server-darwin-arm64
chmod +x server/aiwolf-nlp-server-darwin-arm64
```

macOS (Intel):
```bash
curl -L https://github.com/aiwolfdial/aiwolf-nlp-server/releases/latest/download/aiwolf-nlp-server-darwin-amd64 \
  -o server/aiwolf-nlp-server-darwin-amd64
chmod +x server/aiwolf-nlp-server-darwin-amd64
```

> サーバーバイナリはgitignore対象のため、クローン後に各自ダウンロードしてください。

---

### ② ゲームサーバーを起動（ターミナル1）

**9人村（デフォルト）:**
```bash
./server/aiwolf-nlp-server-darwin-arm64 -c ./server/default_9.yml
```

**5人村に切り替える場合:**
```bash
./server/aiwolf-nlp-server-darwin-arm64 -c ./server/default_5.yml
```

---

### ③ エージェントを起動（ターミナル2）

**APIを使う場合（本番・高性能テスト）:**
```bash
uv run python src/main.py -c ./config/config_koji_jp_v4.yml
```

**Ollamaでローカルテストする場合:**

事前に [Ollama](https://ollama.com) をインストールしてモデルをダウンロード:
```bash
ollama pull smollm2:135m   # 最軽量（動作確認用）
ollama pull phi3:mini      # 性能重視
```

Ollamaサーバーを起動してからエージェントを実行:
```bash
# ターミナル1でOllama起動
ollama serve

# ターミナル2でサーバー起動
./server/aiwolf-nlp-server-darwin-arm64 -c ./server/default_9.yml

# ターミナル3でエージェント起動
uv run python src/main.py -c ./config/config_koji_local.yml
```

---

## 設定ファイル

### エージェント設定 (`config/`)

| ファイル | 用途 |
|---------|------|
| `config_koji_jp_v4.yml` | **本番用**（Google Gemini API、9人村） |
| `config_koji_local.yml` | **ローカルテスト用**（Ollama、9人村） |
| `.env` | APIキー（gitignore対象・要作成） |
| `.env.example` | APIキーのテンプレート |

### サーバー設定 (`server/`)

| ファイル | 用途 |
|---------|------|
| `default_9.yml` | **9人村**（デフォルト） |
| `default_5.yml` | 5人村 |
| `default_5_2Teams.yml` | 5人村・2チーム対戦用 |

---

## 5人村 ↔ 9人村 の切り替え

| 変更箇所 | 9人村 | 5人村 |
|---------|-------|-------|
| サーバー設定 | `default_9.yml` | `default_5.yml` |
| `config_koji_jp_v4.yml` の `agent.num` | `9` | `5` |
| `config_koji_local.yml` の `agent.num` | `9` | `5` |

---

## ディレクトリ構成

```
aiwolf/
├── config/
│   ├── config_koji_jp_v4.yml   # 本番用エージェント設定
│   ├── config_koji_local.yml   # ローカルテスト用
│   ├── .env                    # APIキー（要作成）
│   └── .env.example            # APIキーテンプレート
├── server/
│   ├── default_9.yml           # 9人村サーバー設定
│   ├── default_5.yml           # 5人村サーバー設定
│   ├── default_5_2Teams.yml    # 2チーム対戦用
│   └── Dockerfile              # サーバー用Docker
├── src/
│   ├── main.py                 # エントリーポイント
│   ├── starter.py              # 接続管理
│   ├── agent/                  # エージェント実装
│   └── utils/                  # ユーティリティ
├── Dockerfile                  # エージェント用Docker
├── docker-compose.yml          # Docker Compose
└── pyproject.toml              # 依存関係定義
```

---

## Docker での実行（オプション）

```bash
cp config/.env.example config/.env
# config/.env を編集

docker compose up --build
```

デフォルトで `default_9.yml` と `config_koji_jp_v4.yml` を使用します。
環境変数で変更可能:
```bash
SERVER_CONFIG=default_5.yml CONFIG_FILE=./config/config_koji_local.yml docker compose up
```
