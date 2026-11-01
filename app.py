import hmac
import logging
import os
import re
import time

import streamlit as st

from copilot_nodes import NODE_CATALOG, SOURCE_URL
from flow_diagram import (
    DEEPSEEK_BASE_URL,
    MODEL,
    build_mermaid,
    generate_diagram,
    mermaid_html,
    normalize_result,
)
from flow_validation import summarize_checks, validate_flow

logger = logging.getLogger(__name__)

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 60
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+!|>])")


def _escape_markdown(text) -> str:
    """LLM 由来のテキストを Markdown リンク等として解釈させない."""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", str(text))


def _friendly_error(exc: Exception) -> str:
    """上流 API の詳細をそのまま画面に出さない."""
    if isinstance(exc, ValueError):
        return str(exc)
    text = str(exc).lower()
    if any(
        key in text
        for key in ("401", "unauthorized", "authentication", "api key")
    ):
        return (
            "DeepSeek API の認証に失敗しました。"
            "DEEPSEEK_API_KEY を確認してください。"
        )
    if "timeout" in text or "timed out" in text:
        return "LLM の応答がタイムアウトしました。時間をおいて再試行してください。"
    return "生成処理でエラーが発生しました。管理者にログを確認してください。"


st.set_page_config(
    page_title="Copilot Studio Flow ブロックダイアグラム生成",
    page_icon="🧩",
    layout="wide",
)

# ---------------------------------------------------------------- 認証
def _require_password() -> None:
    """起動時に PASS_KEY によるパスワードチェックを行う。"""
    pass_key = os.environ.get("PASS_KEY", "")
    if not pass_key:
        st.error(
            "環境変数 `PASS_KEY` が設定されていません。"
            "アプリを起動する前に `export PASS_KEY=...` を設定してください。"
        )
        st.stop()

    if st.session_state.get("authenticated", False):
        return

    now = time.time()
    lockout_until = st.session_state.get("lockout_until", 0)
    if lockout_until and now >= lockout_until:
        st.session_state.login_attempts = 0
        st.session_state.lockout_until = 0
        lockout_until = 0
    if now < lockout_until:
        wait_seconds = int(lockout_until - now) + 1
        st.error(
            "試行回数が上限に達しました。"
            f"{wait_seconds} 秒後に再試行してください。"
        )
        st.stop()

    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0

    st.title("Copilot Studio Flow ブロックダイアグラム生成")
    st.caption("起動にはパスワードが必要です。")
    with st.form("login_form"):
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン", type="primary")

    if submitted:
        if hmac.compare_digest(
            password.encode("utf-8"),
            pass_key.encode("utf-8"),
        ):
            st.session_state.authenticated = True
            st.session_state.login_attempts = 0
            st.session_state.lockout_until = 0
            st.rerun()
        else:
            attempts = st.session_state.login_attempts + 1
            st.session_state.login_attempts = attempts
            if attempts >= MAX_LOGIN_ATTEMPTS:
                st.session_state.lockout_until = (
                    time.time() + LOGIN_LOCKOUT_SECONDS
                )
                st.rerun()
            else:
                st.error(
                    "パスワードが正しくありません。"
                    f"（{attempts}/{MAX_LOGIN_ATTEMPTS}）"
                )

    st.stop()


_require_password()

# ---------------------------------------------------------------- UI
st.title("Copilot Studio Flow ブロックダイアグラム生成")
st.caption(
    "自然言語で実現したい機能を入力すると、"
    "Microsoft Learn の Copilot Studio ドキュメント"
    "（ローカル参照: `microsoft-copilot-studio.pdf`）に記載された "
    "ブロックだけを使って Copilot Studio Flow のブロックダイアグラムを"
    "生成・表示します。"
)
st.caption(f"参照元: [Microsoft Learn: Microsoft Copilot Studio]({SOURCE_URL})")

with st.sidebar:
    st.header("設定")
    if st.button("ログアウト"):
        st.session_state.authenticated = False
        st.rerun()
    if os.environ.get("DEEPSEEK_API_KEY"):
        st.success("`DEEPSEEK_API_KEY`: 設定済み")
    else:
        st.error("`DEEPSEEK_API_KEY`: 未設定")
    st.markdown(f"**モデル**: `{MODEL}`")
    st.markdown(f"**API Base URL**: `{DEEPSEEK_BASE_URL}`")

    with st.expander("使用可能なノード（参照元準拠）", expanded=False):
        for node in NODE_CATALOG:
            st.markdown(
                f"- **{node['name']}**（`{node['key']}`）\n"
                f"  {node['category']} / PDF p.{node['pdf_page']}"
            )

examples = {
    "問い合わせ対応（トピック）": (
        "ユーザーからの問い合わせを受け付け、問い合わせ種別を聞いて、"
        "返品なら返品方法を案内し、その他は有人窓口に引き継ぐ"
    ),
    "メール分類（ワークフロー）": (
        "メールが届いたら本文を「苦情」「問い合わせ」「営業」に分類し、"
        "苦情なら Teams の担当者チャネルに通知する"
    ),
    "請求書処理（ワークフロー）": (
        "請求書PDFを受け取り、請求日・請求元・合計金額と明細を抽出して、"
        "承認のために担当者へ情報を要求する"
    ),
}

if "user_input" not in st.session_state:
    st.session_state.user_input = ""
if "result" not in st.session_state:
    st.session_state.result = None
if "error" not in st.session_state:
    st.session_state.error = None

st.markdown("#### サンプル")
sample_cols = st.columns(len(examples))
for col, (label, text) in zip(sample_cols, examples.items()):
    if col.button(label, key=f"sample_{label}"):
        st.session_state.user_input = text

with st.form("input_form"):
    user_input = st.text_area(
        "実現したい機能を自然言語で入力してください",
        key="user_input",
        height=140,
        max_chars=4000,
        help="最大4,000文字まで入力できます。",
        placeholder="例: 上司からのメールが届いたら、本文を要約して Teams のアナウンスチャネルに投稿する",
    )
    submitted = st.form_submit_button(
        "ブロックダイアグラムを生成", type="primary"
    )

if submitted:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        st.error(
            "環境変数 `DEEPSEEK_API_KEY` が設定されていません。"
            "ターミナルで `export DEEPSEEK_API_KEY=...` を実行してからアプリを起動してください。"
        )
        st.stop()
    if not user_input.strip():
        st.session_state.result = None
        st.session_state.error = None
        st.warning("自然言語の要件を入力してください。")
        st.stop()
    else:
        with st.spinner(f"DeepSeek {MODEL} でフローを生成中…"):
            try:
                raw_data = generate_diagram(user_input)
                normalized = normalize_result(raw_data)
                mermaid_code = build_mermaid(normalized)
                st.session_state.result = {
                    "data": normalized,
                    "mermaid": mermaid_code,
                }
                st.session_state.error = None
            except Exception as exc:  # noqa: BLE001 - ユーザーへ原因を表示する
                logger.exception("Diagram generation failed")
                st.session_state.result = None
                st.session_state.error = _friendly_error(exc)

if st.session_state.error:
    st.error(
        "生成に失敗しました: "
        + _escape_markdown(st.session_state.error)
    )

if st.session_state.result:
    result = st.session_state.result
    data = result["data"]

    st.subheader(_escape_markdown(data.get("title") or "無題のフロー"))
    if data.get("harness"):
        st.caption(f"ハーネス: {_escape_markdown(data['harness'])}")
    if data.get("notes"):
        st.info(_escape_markdown(data["notes"]))

    tab_diagram, tab_detail, tab_validation, tab_mermaid, tab_json = st.tabs(
        [
            "ブロックダイアグラム",
            "ノード詳細",
            "検証",
            "Mermaidコード",
            "生成JSON",
        ]
    )

    with tab_diagram:
        st.caption(
            "図の上部にある「PNGをダウンロード」から、"
            "ブロックダイアグラムを PNG 画像として保存できます。"
        )
        st.iframe(
            mermaid_html(result["mermaid"]),
            width="stretch",
            height=760,
        )

    with tab_detail:
        for index, node in enumerate(data["nodes"], start=1):
            st.markdown(
                f"### {index}. {_escape_markdown(node['name'])}"
            )
            st.markdown(
                f"**処理概要**: {_escape_markdown(node['label'])}"
            )
            st.markdown(
                f"**カテゴリ**: {_escape_markdown(node['category'])}"
            )
            st.markdown("**指定すべきパラメータ（設定値の参考例）**")
            for param in node["parameters"]:
                st.markdown(
                    f"- **{_escape_markdown(param['name'])}**: "
                    f"{_escape_markdown(param['value'])}"
                )
            supports_prompt = node.get(
                "supports_prompt",
                node["type"]
                not in {"topic_trigger", "flow_trigger", "workflow_trigger"},
            )
            if supports_prompt:
                st.markdown(
                    "**指示プロンプト例**: "
                    f"{_escape_markdown(node['prompt'])}"
                )
            elif node["type"] in {
                "topic_trigger",
                "flow_trigger",
                "workflow_trigger",
            }:
                st.markdown("**指示プロンプト**: トリガーには設定しません。")
            else:
                st.markdown(
                    "**指示プロンプト**: 条件・終了・変数設定は "
                    "parameters と next で表現するため設定しません。"
                )
            st.divider()

    with tab_validation:
        checks = validate_flow(data)
        summary = summarize_checks(checks)

        if summary["passed"]:
            st.success(
                "合格: 必須チェックをすべて通過しました。"
                f"（PASS {summary['pass_count']} / "
                f"WARN {summary['warn_count']}）"
            )
        else:
            st.error(
                f"不合格: 必須チェック {summary['fail_count']} 件が"
                "失敗しています。"
                f"（PASS {summary['pass_count']} / "
                f"WARN {summary['warn_count']}）"
            )

        metric_cols = st.columns(3)
        metric_cols[0].metric("PASS", summary["pass_count"])
        metric_cols[1].metric("WARN", summary["warn_count"])
        metric_cols[2].metric("FAIL", summary["fail_count"])

        status_labels = {
            "pass": "✅ PASS",
            "warn": "⚠️ WARN",
            "fail": "❌ FAIL",
        }
        rows = [
            {
                "種別": "必須" if check.required else "推奨",
                "カテゴリ": check.category,
                "チェック項目": check.item,
                "結果": status_labels[check.status],
                "詳細": check.detail,
            }
            for check in checks
        ]
        st.dataframe(rows, width="stretch", hide_index=True)

        with st.expander("検証の基準"):
            st.markdown(
                "- **必須**: 失敗すると「不合格」になります。\n"
                "- **推奨**: 失敗すると「WARN」になりますが、合否には影響しません。\n"
                "- 検証対象: PDF記載のノード種別、トリガー、接続、到達性、"
                "終了処理、パラメータ、分岐、指示プロンプトなど。"
            )

    with tab_mermaid:
        st.code(result["mermaid"], language="mermaid")

    with tab_json:
        st.json(data)
