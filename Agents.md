# Copilot Studio Flow Designer

## プロジェクト要件（ユーザー指示・原文）

microsoft-copilot-studio.pdfに記載されている内容を参考にして、ユーザからの自然言語による入力に対して、その機能を実現するためのCopilt Studio Flowのブロックダイアグラムを作成して表示するアプリを作成してください。使用するブロックダイアグラムは、必ずmicrosoft-copilot-studio.pdfの中で規定されているもの使い、勝手に創作しないでください。
また、各ブロックダイアグラムの中で指定すべきパラメータ、指示プロンプトを参考例として記述するようにしてください。
アプリケーションの実行環境としては、Streamlit／Python3.11を前提とし、LLMは、DeepSeekのdeepseek-flashモデルを使ってください。
尚、DeepSeekのAPIキーは環境変数：DEEPSEEK_API_KEYから取得するようにしてください。

## 概要

- 自然言語で要求された機能を Copilot Studio Flow のブロックダイアグラムに変換し、Streamlit 上に表示するアプリ。
- ブロック／ノードは `microsoft-copilot-studio.pdf` に記載された定義だけを使い、勝手に創作しない。
- 各ブロックには、設定すべきパラメータと指示プロンプトの参考例を併記する。
- 生成結果は「検証」タブでチェックリストを自動実行し、合否（PASS／WARN／FAIL）を表示する。
- 1つのフロー内で異なるハーネス（エージェント トピック／エージェントフロー／ワークフロー）を混在させない。
- トリガーには指示プロンプトを設定しない（トリガー条件のみ設定する）。
- RFI は「担当者（Assignees）」を使い、メッセージ本文に抽出結果を動的コンテンツ（`{{...}}`）で埋め込む。
- 請求書抽出では請求書番号・税額・通貨も抽出項目に含める。
- メール分類では件名と本文を結合し、受信フォルダ・自動返信・配信停止・自分宛て以外の除外条件を設計する。
- 分類の迷い時は苦情寄り、または「要確認」カテゴリを用意する。
- Teams 投稿は `workflow_action` で固定し、`agent_node` は要約・分類に限定する。メール本文は信頼できない入力として扱う。
- 二重通知防止、投稿失敗時の再試行／代替通知、問い合わせ・営業の振り分け／ログを設計する。

## 技術スタック

- Streamlit / Python 3.11。このマシンの既定 `python3` は 3.10.9 のため、3.11 は pyenv 経由で `PYENV_VERSION=3.11.9 python` を使う（pyenv には 3.11.0 / 3.11.9 が導入済み）。
- LLM は DeepSeek の `deepseek-flash` 固定。APIキーは環境変数 `DEEPSEEK_API_KEY` から取得する。
- `DEEPSEEK_API_KEY` 未設定時は生成を止め、明確なエラーを表示する。
- 起動時のパスワードチェックは環境変数 `PASS_KEY` を使用する。未設定時はアプリを表示しない。5回失敗で60秒ロックする。

## ブロック定義の参照元

- Microsoft Learn: https://learn.microsoft.com/ja-jp/microsoft-copilot-studio/
- ローカル参照: `microsoft-copilot-studio.pdf`（2595ページ、日本語ドキュメント）。GitHub には含めない（`.gitignore` で除外）。

実装時は上記ドキュメントから対象ノード種別・パラメータを抽出し、そのカタログだけを LLM に渡して選択させる。

主要な定義ページ（PyPDF2 の 0-based ページ番号）:

- 標準エージェントフロー: メッセージ p.764 / 質問 p.772 / 条件 p.791 / トリガー概要 p.932
- エージェントフロー: 概要 p.2019 / 自然言語で構築 p.2024 / エージェントノード p.2031 / プロンプトノード p.2036
- ワークフロー (GitHub Copilot harness): エージェントノード p.1978 / Copilotノード p.1990 / 分類ノード p.1997 / 抽出ノード p.2002

## 検証済みのローカル手順

```
export PASS_KEY=任意のパスワード
PYENV_VERSION=3.11.9 python -m venv .venv
.venv/bin/pip install -r requirements.txt   # streamlit / openai が導入可能（検証済み: streamlit 1.66.1）
.venv/bin/streamlit run app.py
```

## 完了条件

- `.venv/bin/streamlit run app.py` で起動し、自然言語入力に対してブロックダイアグラムが表示される。
- 出力された全ブロックが PDF 記載の定義に対応している（未定義ブロックを含まない）。
- 各ブロックにパラメータ／指示プロンプトの参考例が表示される。
- 生成したブロックダイアグラムを PNG 画像としてダウンロードできる。
- 「検証」タブでチェックリストを自動実行し、合否と PASS／WARN／FAIL の内訳を表示できる。
- ハーネス混在がないこと、トリガーに指示プロンプトがないことを検証できる。
- `DEEPSEEK_API_KEY` 未設定時に明確なエラーになる。
- `PASS_KEY` 未設定時はアプリを表示せず、誤ったパスワードではメイン画面に進めない。
