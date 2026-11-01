# Copilot Studio Flow Designer

自然言語で説明した業務要件を、Microsoft Copilot Studio Flow のブロックダイアグラムに変換し、Streamlit 上で表示するアプリです。生成された図は Mermaid で描画され、PNG 画像としてダウンロードできます。

## 主な機能

- 自然言語入力から Copilot Studio Flow のブロックダイアグラムを生成
- `microsoft-copilot-studio.pdf` および Microsoft Learn の Copilot Studio ドキュメントに記載されたノードだけを使用
- 各ノードに「指定すべきパラメータ」と「指示プロンプトの参考例」を表示
- Mermaid によるブロックダイアグラム描画
- ブロックダイアグラムの PNG ダウンロード
- 「検証」タブによる自動チェック
  - PDF 記載のノード種別
  - ハーネス混在（エージェント トピック／エージェントフロー／ワークフロー）
  - トリガー、接続、到達性、終了処理
  - パラメータ項目・値
  - 条件分岐・分類分岐
  - RFI の担当者（Assignees）・動的コンテンツ
  - メール分類・Teams 通知の運用
- `PASS_KEY` による起動時パスワードチェック
- DeepSeek `deepseek-flash` 固定

## 必要要件

- Python 3.11
- Streamlit 1.66.1 / OpenAI 2.32.0（`requirements.txt` で固定）
- DeepSeek API キー
- ブラウザから Mermaid CDN にアクセスできること（図の描画・PNG 変換に使用）

## セットアップ

```bash
cd CopilotSudioFlowDesigner

export PASS_KEY=任意のパスワード
export DEEPSEEK_API_KEY=あなたのDeepSeekAPIキー

PYENV_VERSION=3.11.9 python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Python 3.11 を直接利用できる場合:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

## 環境変数

| 変数 | 必須 | 説明 |
|---|---|---|
| `PASS_KEY` | 必須 | アプリ起動時のパスワード。未設定時はアプリを表示しない。 |
| `DEEPSEEK_API_KEY` | 必須 | DeepSeek API のキー。未設定時は生成を停止してエラーを表示する。 |

`PASS_KEY` と `DEEPSEEK_API_KEY` はソースコードに直接書かず、環境変数または `.env` などで管理してください。`.env` は `.gitignore` で除外されています。

## 使い方

1. アプリ起動時にパスワードを入力します。
2. 実現したい機能を自然言語で入力します。
3. 「ブロックダイアグラムを生成」をクリックします。
4. 生成結果を以下のタブで確認します。
   - **ブロックダイアグラム**: Mermaid で描画されたフロー
   - **ノード詳細**: 各ノードのパラメータと指示プロンプト例
   - **検証**: 自動チェックの合否（PASS／WARN／FAIL）
   - **Mermaidコード**: 生成された Mermaid コード
   - **生成JSON**: LLM が返した構造化データ
5. 図の上部にある「PNGをダウンロード」から画像を保存します。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `app.py` | Streamlit UI、パスワードチェック、生成結果の表示 |
| `flow_diagram.py` | DeepSeek API 呼び出し、JSON 正規化、Mermaid コード生成、PNG 変換 HTML |
| `copilot_nodes.py` | PDF から抽出したノードカタログとパラメータ定義 |
| `flow_validation.py` | ブロックダイアグラムの自動検証ロジック |
| `requirements.txt` | Python 依存パッケージ |
| `.streamlit/config.toml` | エラー詳細の非表示、CORS/XSRF 設定 |
| `Agents.md` | 開発・運用上のプロジェクト指示 |
| `.gitignore` | 仮想環境、`.env`、PDF などの除外設定 |
| `LICENSE` | MIT ライセンス |

## ノードカタログ

`copilot_nodes.py` の `NODE_CATALOG` に、PDF から抽出したノードを定義しています。主な分類は以下です。

- エージェント トピック（標準ハーネス）
- エージェントフロー（標準ハーネス）
- ワークフロー（GitHub Copilot harness）

1つのフロー内で異なるハーネスを混在させないよう、生成プロンプトと検証タブの両方でチェックします。トリガーには指示プロンプトを設定しません。

## 参照ドキュメント

- Microsoft Learn: <https://learn.microsoft.com/ja-jp/microsoft-copilot-studio/>
- 参照日: **2026年10月31日**
- ローカル参照: `microsoft-copilot-studio.pdf`
  - GitHub には含めません（`.gitignore` で除外）。
  - 必要な場合は Microsoft Learn から取得してください。

## セキュリティと公開時の注意

- `PASS_KEY` は起動時の簡易認証です。5回失敗すると60秒間ロックします（セッション単位）。SSO・MFA の代替ではありません。
- インターネットに公開する場合は、HTTPS 終端のリバースプロキシや SSO を前段に置き、Streamlit を直接公開しないでください。
- `DEEPSEEK_API_KEY` はサーバー側でのみ使用します。
- `.env` や `.streamlit/secrets.toml` はコミットしないでください。`.gitignore` で除外済みです。
- `.streamlit/config.toml` で `client.showErrorDetails = "none"` を設定し、例外の詳細を画面に出さないようにしています。
- 入力は4,000文字、ノード数は50件、接続数は200件、APIタイムアウトは60秒に制限しています。
- Mermaid は `10.9.8` を SRI（Subresource Integrity）付きで読み込みます。CDN障害時は図が表示されないため、必要に応じて同梱を検討してください。
- Python 依存パッケージは `requirements.txt` でバージョンを固定しています。

## 制約・注意事項

- LLM は DeepSeek の `deepseek-flash` 固定です。
- 図の描画と PNG 変換には Mermaid の CDN を利用します。CDN にアクセスできない環境では図と PNG が表示できません。
- PDF はローカル参照用です。リポジトリには含めていません。
- 生成結果は設計の参考例です。実際の Copilot Studio の画面・バージョンによって、ノード名や設定項目が異なる場合があります。
- 生成結果を業務で利用する前に、Microsoft Learn の最新ドキュメントと実際の画面で確認してください。

## ライセンス

MIT License. 詳細は [LICENSE](LICENSE) を参照してください。
