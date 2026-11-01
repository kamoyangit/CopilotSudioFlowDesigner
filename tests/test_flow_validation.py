import unittest

from flow_diagram import normalize_result
from flow_validation import summarize_checks, validate_flow


def _p(name: str, value: str) -> dict:
    return {"name": name, "value": value}


def _node(
    node_id: str,
    node_type: str,
    label: str,
    parameters: list,
    next_nodes=(),
    prompt: str = "",
) -> dict:
    return {
        "id": node_id,
        "type": node_type,
        "label": label,
        "parameters": parameters,
        "prompt": prompt,
        "next": [
            {"to": to, "label": branch_label}
            for to, branch_label in next_nodes
        ],
    }


def _end(node_id: str, label: str, next_nodes=()) -> dict:
    return _node(
        node_id,
        "end_conversation",
        label,
        [
            _p("終了メッセージ（トピックの場合。ワークフローでは空でよい）", ""),
            _p("アンケート", "なし"),
            _p("通話後アクション", "なし"),
        ],
        next_nodes,
    )


class StructuredFlowValidationTest(unittest.TestCase):
    def test_email_classification_flow_is_structural(self):
        """条件・終了・変数設定・重複チェック・エラー処理を独立ノードにする."""
        raw = {
            "title": "メール分類＋苦情通知（構造化）",
            "harness": "ワークフロー（GitHub Copilot harness）",
            "nodes": [
                _node(
                    "n1",
                    "workflow_trigger",
                    "Outlook で受信メールを受け取る",
                    [
                        _p("トリガータイプ", "イベント"),
                        _p("コネクタとイベント", "Outlook で新しいメールが届いたとき"),
                        _p(
                            "受信フォルダ／自分宛て",
                            "受信トレイ。共有メールボックスなので自分宛ては空",
                        ),
                        _p("コネクタのトリガー出力", "メッセージID、件名、本文"),
                    ],
                    [("n2", "")],
                ),
                _node(
                    "n2",
                    "set_variable",
                    "HTML本文をテキスト化",
                    [
                        _p("変数名", "BodyText"),
                        _p(
                            "値または Power Fx 数式",
                            "PlainText(triggerOutputs()?['body/body'])",
                        ),
                        _p("スコープ", "フロー変数"),
                    ],
                    [("n3", "")],
                ),
                _node(
                    "n3",
                    "set_variable",
                    "分類用入力を生成",
                    [
                        _p("変数名", "ClassificationInput"),
                        _p("値または Power Fx 数式", "件名 & 改行 & BodyText"),
                        _p("スコープ", "フロー変数"),
                    ],
                    [("n4", "")],
                ),
                _node(
                    "n4",
                    "set_variable",
                    "本文抜粋を生成",
                    [
                        _p("変数名", "BodyExcerpt"),
                        _p("値または Power Fx 数式", "Left(BodyText, 300)"),
                        _p("スコープ", "フロー変数"),
                    ],
                    [("n5", "")],
                ),
                _node(
                    "n5",
                    "condition",
                    "自動返信・配信停止の除外",
                    [
                        _p("左辺の変数", "件名 & BodyText"),
                        _p("演算子", "contains"),
                        _p(
                            "右辺の値",
                            "自動返信, Auto-Reply, 配信停止, unsubscribe",
                        ),
                        _p("分岐", "next のラベルで表現"),
                    ],
                    [("n6", "真: 除外に該当"), ("n7", "偽: 次へ")],
                ),
                _end("n6", "正常終了（除外）"),
                _node(
                    "n7",
                    "workflow_action",
                    "SharePoint 項目の取得（重複チェック）",
                    [
                        _p("コネクタとアクション", "SharePoint 項目の取得"),
                        _p("接続", "SharePoint"),
                        _p(
                            "入力パラメータ",
                            "メッセージID eq 'triggerOutputs()?['body/messageId']'",
                        ),
                        _p("設定（Settings）", "取得件数を出力"),
                        _p("出力", "取得件数"),
                    ],
                    [("n8", "")],
                ),
                _node(
                    "n8",
                    "condition",
                    "重複あり?",
                    [
                        _p("左辺の変数", "取得件数"),
                        _p("演算子", ">"),
                        _p("右辺の値", "0"),
                        _p("分岐", "next のラベルで表現"),
                    ],
                    [("n6", "真: 重複あり"), ("n9", "偽: 重複なし")],
                ),
                _node(
                    "n9",
                    "workflow_action",
                    "ログ作成（全件共通）",
                    [
                        _p("コネクタとアクション", "SharePoint 項目の作成"),
                        _p("接続", "SharePoint"),
                        _p(
                            "入力パラメータ",
                            "受信日時、差出人、件名、分類ラベル、"
                            "メッセージID、通知状態=未通知、振り分け先",
                        ),
                        _p(
                            "設定（Settings）",
                            "振り分け先は営業→営業担当、"
                            "それ以外→サポート担当",
                        ),
                        _p("出力", "作成された項目ID"),
                    ],
                    [("n10", "")],
                ),
                _node(
                    "n10",
                    "classify_node",
                    "分類",
                    [
                        _p(
                            "入力テキスト",
                            "ClassificationInput（件名＋本文テキスト）",
                        ),
                        _p(
                            "カテゴリ名と判定条件",
                            "苦情: 不満・損害・要求の根拠が1つ以上／"
                            "問い合わせ: 単なる質問／営業: 売り込み／"
                            "要確認: 根拠なし",
                        ),
                        _p(
                            "カテゴリごとの入力例",
                            "苦情: 返金してほしい／"
                            "問い合わせ: 仕様を教えて／"
                            "営業: 新製品の案内／要確認: 判断不能",
                        ),
                        _p("出力変数", "Category"),
                    ],
                    [
                        ("n11", "苦情"),
                        ("n16", "問い合わせ"),
                        ("n16", "営業"),
                        ("n16", "要確認"),
                    ],
                    "根拠が1つでもあれば苦情、単なる質問は問い合わせ、"
                    "売り込みは営業、根拠がなければ要確認",
                ),
                _node(
                    "n11",
                    "workflow_action",
                    "Teams 投稿",
                    [
                        _p(
                            "コネクタとアクション",
                            "Microsoft Teams チャネルにメッセージを投稿",
                        ),
                        _p("接続", "Microsoft Teams"),
                        _p(
                            "入力パラメータ",
                            "投稿先: サポートチャネル、"
                            "メッセージ: BodyExcerpt"
                            "（先頭300文字、プレーンテキスト）",
                        ),
                        _p(
                            "設定（Settings）",
                            "再試行ポリシー: 指数バックオフ、3回",
                        ),
                        _p(
                            "出力",
                            "実行結果（投稿IDや成功フラグは使わない）",
                        ),
                    ],
                    [("n12", "")],
                ),
                _node(
                    "n12",
                    "condition",
                    "Teams 投稿の成否",
                    [
                        _p("左辺の変数", "Teams 投稿の実行結果"),
                        _p("演算子", "="),
                        _p("右辺の値", "失敗"),
                        _p("分岐", "next のラベルで表現"),
                    ],
                    [("n14", "真: 失敗"), ("n13", "偽: 成功")],
                ),
                _node(
                    "n13",
                    "set_variable",
                    "通知状態＝通知済み",
                    [
                        _p("変数名", "NotificationStatus"),
                        _p("値または Power Fx 数式", "通知済み"),
                        _p("スコープ", "フロー変数"),
                    ],
                    [("n13a", "")],
                ),
                _node(
                    "n13a",
                    "workflow_action",
                    "SharePoint 更新（通知済み）",
                    [
                        _p("コネクタとアクション", "SharePoint 項目の更新"),
                        _p("接続", "SharePoint"),
                        _p(
                            "入力パラメータ",
                            "作成された項目ID、通知状態=通知済み",
                        ),
                        _p("設定（Settings）", "作成項目IDを使用"),
                        _p("出力", "更新結果"),
                    ],
                    [("n16", "")],
                ),
                _node(
                    "n14",
                    "workflow_action",
                    "Outlook 代替通知",
                    [
                        _p("コネクタとアクション", "Outlook メールの送信 (V2)"),
                        _p("接続", "Office 365 Outlook"),
                        _p(
                            "入力パラメータ",
                            "宛先: 担当者グループ、本文: BodyExcerpt",
                        ),
                        _p("設定（Settings）", "Teams 投稿失敗時のみ実行"),
                        _p("出力", "送信結果"),
                    ],
                    [("n15", "")],
                ),
                _node(
                    "n15",
                    "set_variable",
                    "通知状態＝代替通知済み",
                    [
                        _p("変数名", "NotificationStatus"),
                        _p("値または Power Fx 数式", "代替通知済み"),
                        _p("スコープ", "フロー変数"),
                    ],
                    [("n15a", "")],
                ),
                _node(
                    "n15a",
                    "workflow_action",
                    "SharePoint 更新（代替通知済み）",
                    [
                        _p("コネクタとアクション", "SharePoint 項目の更新"),
                        _p("接続", "SharePoint"),
                        _p(
                            "入力パラメータ",
                            "作成された項目ID、通知状態=代替通知済み",
                        ),
                        _p("設定（Settings）", "作成項目IDを使用"),
                        _p("出力", "更新結果"),
                    ],
                    [("n16", "")],
                ),
                _end("n16", "正常終了"),
            ],
        }

        data = normalize_result(raw)
        checks = validate_flow(data)
        summary = summarize_checks(checks)
        items = {check.item: check.status for check in checks}

        self.assertEqual(summary["fail_count"], 0)
        self.assertEqual(items["ハーネス混在"], "pass")
        self.assertEqual(items["受信メールの除外条件"], "pass")
        self.assertEqual(items["通知の運用"], "pass")
        self.assertEqual(items["ログ作成（全件共通）"], "pass")
        self.assertEqual(items["分類の判定ルール"], "pass")
        self.assertEqual(items["条件分岐の本数"], "pass")


if __name__ == "__main__":
    unittest.main()
