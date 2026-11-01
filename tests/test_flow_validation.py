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
        """条件・初期化・Try/Catch・ログ・代替通知を独立ノードにする."""
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
                            "受信トレイ。自分宛て: 指定なし＝全メール対象",
                        ),
                        _p(
                            "コネクタのトリガー出力",
                            "MessageID、件名、本文、差出人、受信日時",
                        ),
                    ],
                    [("n2", "")],
                ),
                _node(
                    "n2",
                    "workflow_action",
                    "HTMLからテキスト",
                    [
                        _p("コネクタとアクション", "HTMLからテキスト"),
                        _p("接続", "組み込み"),
                        _p("入力パラメータ", "triggerOutputs()?['body/body']"),
                        _p("設定（Settings）", "なし"),
                        _p("出力", "Text"),
                    ],
                    [("n3", "")],
                    "HTML本文をプレーンテキストに変換する",
                ),
                _node(
                    "n3",
                    "set_variable",
                    "本文テキストを初期化",
                    [
                        _p("変数名", "BodyText"),
                        _p("値または Power Automate 式", "outputs('HTMLからテキスト')"),
                        _p("初期化／更新", "初期化"),
                        _p("スコープ", "フロー変数"),
                    ],
                    [("n4", "")],
                ),
                _node(
                    "n4",
                    "set_variable",
                    "分類用入力を初期化",
                    [
                        _p("変数名", "ClassificationInput"),
                        _p(
                            "値または Power Automate 式",
                            "concat(triggerOutputs()?['body/subject'], "
                            "char(10), variables('BodyText'))",
                        ),
                        _p("初期化／更新", "初期化"),
                        _p("スコープ", "フロー変数"),
                    ],
                    [("n5", "")],
                ),
                _node(
                    "n5",
                    "set_variable",
                    "本文抜粋を初期化",
                    [
                        _p("変数名", "BodyExcerpt"),
                        _p(
                            "値または Power Automate 式",
                            "substring(variables('BodyText'), 0, "
                            "min(300, length(variables('BodyText'))))",
                        ),
                        _p("初期化／更新", "初期化"),
                        _p("スコープ", "フロー変数"),
                    ],
                    [("n6", "")],
                ),
                _node(
                    "n6",
                    "set_variable",
                    "通知状態を初期化",
                    [
                        _p("変数名", "NotificationStatus"),
                        _p("値または Power Automate 式", "'通知不要'"),
                        _p("初期化／更新", "初期化"),
                        _p("スコープ", "フロー変数"),
                    ],
                    [("n7", "")],
                ),
                _node(
                    "n7",
                    "condition",
                    "自動返信・配信停止の除外",
                    [
                        _p(
                            "左辺の変数",
                            "concat(triggerOutputs()?['body/subject'], "
                            "variables('BodyText'))",
                        ),
                        _p("演算子", "contains"),
                        _p(
                            "右辺の値",
                            "自動返信, Auto-Reply, 配信停止, unsubscribe",
                        ),
                        _p("分岐", "next のラベルで表現"),
                    ],
                    [("n8", "真: 除外に該当 → 正常終了"), ("n9", "偽: 次へ")],
                ),
                _end("n8", "正常終了（除外）"),
                _node(
                    "n9",
                    "workflow_action",
                    "SharePoint 項目の取得（重複チェック）",
                    [
                        _p("コネクタとアクション", "SharePoint 項目の取得"),
                        _p("接続", "SharePoint"),
                        _p(
                            "入力パラメータ",
                            "サイト名: サポートサイト、リスト名: メールログ、"
                            "フィルター: MessageID eq "
                            "'triggerOutputs()?['body/messageId']'",
                        ),
                        _p("設定（Settings）", "取得件数を出力"),
                        _p("出力", "取得件数"),
                    ],
                    [("n10", "")],
                    "SharePoint ログをメッセージID（内部名 MessageID）で検索し、"
                    "結果の件数を返す",
                ),
                _node(
                    "n10",
                    "condition",
                    "重複あり?",
                    [
                        _p("左辺の変数", "取得件数"),
                        _p("演算子", ">"),
                        _p("右辺の値", "0"),
                        _p("分岐", "next のラベルで表現"),
                    ],
                    [("n8", "真: 重複あり → 正常終了"), ("n11", "偽: 重複なし → ログ作成")],
                ),
                _node(
                    "n11",
                    "workflow_action",
                    "SharePoint ログ作成（全件共通）",
                    [
                        _p("コネクタとアクション", "SharePoint 項目の作成"),
                        _p("接続", "SharePoint"),
                        _p(
                            "入力パラメータ",
                            "サイト名: サポートサイト、リスト名: メールログ、"
                            "Title: 件名、受信日時、差出人、件名、分類ラベル、"
                            "MessageID、通知状態=通知不要、振り分け先",
                        ),
                        _p(
                            "設定（Settings）",
                            "振り分け先: 営業→営業担当、"
                            "それ以外→サポート担当",
                        ),
                        _p("出力", "作成された項目ID"),
                    ],
                    [("n12", "")],
                    "分類ラベル・振り分け先を含む全件ログを SharePoint に作成し、"
                    "Title＝件名、作成された項目IDを返す",
                ),
                _node(
                    "n12",
                    "classify_node",
                    "分類",
                    [
                        _p("入力テキスト", "ClassificationInput（件名＋本文テキスト）"),
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
                        ("n13", "苦情 → Teams 投稿（Try）"),
                        ("n18", "問い合わせ／営業／要確認 → 正常終了"),
                    ],
                    "根拠が1つでもあれば苦情、単なる質問は問い合わせ、"
                    "売り込みは営業、根拠がなければ要確認",
                ),
                _node(
                    "n13",
                    "workflow_action",
                    "Teams 投稿（Try）",
                    [
                        _p(
                            "コネクタとアクション",
                            "Microsoft Teams チャネルにメッセージを投稿",
                        ),
                        _p("接続", "Microsoft Teams"),
                        _p(
                            "入力パラメータ",
                            "投稿先: サポートチャネル、固定フォーマット: "
                            "件名、差出人、受信日時、メッセージID、分類、"
                            "本文抜粋（先頭300文字）。改行は <br> に変換",
                        ),
                        _p(
                            "設定（Settings）",
                            "スコープ（Try/Catch）: Try、"
                            "再試行ポリシー: 指数バックオフ3回、"
                            "失敗／タイムアウト時は Catch へ",
                        ),
                        _p(
                            "出力",
                            "実行結果（投稿IDや成功フラグは使わない）",
                        ),
                    ],
                    [
                        ("n14", "Try: 成功時"),
                        ("n15", "Catch: 失敗／タイムアウト時のみ"),
                    ],
                    "指定チャネルに、件名・差出人・受信日時・メッセージID・"
                    "分類・本文抜粋（先頭300文字）を固定フォーマットで投稿する",
                ),
                _node(
                    "n14",
                    "set_variable",
                    "通知状態＝通知済み（Try）",
                    [
                        _p("変数名", "NotificationStatus"),
                        _p("値または Power Automate 式", "'通知済み'"),
                        _p("初期化／更新", "更新"),
                        _p("スコープ", "Try"),
                    ],
                    [("n17", "")],
                ),
                _node(
                    "n15",
                    "workflow_action",
                    "Outlook 代替通知（Catch）",
                    [
                        _p("コネクタとアクション", "Outlook メールの送信 (V2)"),
                        _p("接続", "Office 365 Outlook"),
                        _p(
                            "入力パラメータ",
                            "宛先: 担当者グループ、件名: 件名、"
                            "本文: 差出人、受信日時、メッセージID、本文抜粋",
                        ),
                        _p(
                            "設定（Settings）",
                            "スコープ（Try/Catch）: Catch、"
                            "実行条件（Run after）: Teams 投稿が失敗／"
                            "タイムアウトした時のみ",
                        ),
                        _p("出力", "送信結果"),
                    ],
                    [("n16", "")],
                    "Teams 投稿が失敗またはタイムアウトした場合に、"
                    "担当者グループへメールで代替通知する",
                ),
                _node(
                    "n16",
                    "set_variable",
                    "通知状態＝代替通知済み（Catch）",
                    [
                        _p("変数名", "NotificationStatus"),
                        _p("値または Power Automate 式", "'代替通知済み'"),
                        _p("初期化／更新", "更新"),
                        _p("スコープ", "Catch"),
                    ],
                    [("n17", "")],
                ),
                _node(
                    "n17",
                    "workflow_action",
                    "SharePoint 更新（Try/Catch後）",
                    [
                        _p("コネクタとアクション", "SharePoint 項目の更新"),
                        _p("接続", "SharePoint"),
                        _p(
                            "入力パラメータ",
                            "サイト名: サポートサイト、リスト名: メールログ、"
                            "作成された項目ID、"
                            "通知状態=variables('NotificationStatus')",
                        ),
                        _p(
                            "設定（Settings）",
                            "実行条件（Run after）: Try 成功または "
                            "Catch 成功後に実行",
                        ),
                        _p("出力", "更新結果"),
                    ],
                    [("n18", "")],
                    "作成済みログ項目の通知状態を、変数の値で更新する",
                ),
                _end("n18", "正常終了"),
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
        self.assertEqual(items["アクションの指示プロンプト"], "pass")
        self.assertEqual(items["式の統一"], "pass")

    def test_action_prompts_are_generated_per_action(self):
        """Teams 投稿の既定プロンプトが他アクションへコピーされない."""
        generic = (
            "Teams の指定チャネルに、前処理で作った本文抜粋を投稿する"
        )
        raw = {
            "title": "アクション別プロンプト",
            "harness": "ワークフロー（GitHub Copilot harness）",
            "nodes": [
                _node(
                    "a1",
                    "workflow_action",
                    "SharePoint 項目の取得",
                    [_p("コネクタとアクション", "SharePoint 項目の取得")],
                    prompt=generic,
                ),
                _node(
                    "a2",
                    "workflow_action",
                    "SharePoint 項目の作成",
                    [_p("コネクタとアクション", "SharePoint 項目の作成")],
                    prompt=generic,
                ),
                _node(
                    "a3",
                    "workflow_action",
                    "Outlook メールの送信",
                    [_p("コネクタとアクション", "Outlook メールの送信")],
                    prompt=generic,
                ),
                _node(
                    "a4",
                    "workflow_action",
                    "SharePoint 項目の更新",
                    [_p("コネクタとアクション", "SharePoint 項目の更新")],
                    prompt=generic,
                ),
            ],
        }

        data = normalize_result(raw)
        prompts = [node["prompt"] for node in data["nodes"]]
        by_label = {node["label"]: node["prompt"] for node in data["nodes"]}

        self.assertEqual(len(prompts), len(set(prompts)))
        self.assertIn("取得", by_label["SharePoint 項目の取得"])
        self.assertIn("作成", by_label["SharePoint 項目の作成"])
        self.assertIn("代替通知", by_label["Outlook メールの送信"])
        self.assertIn("更新", by_label["SharePoint 項目の更新"])

    def test_status_code_and_missing_status_init_warn(self):
        """Teams の statusCode 判定と通知状態の未初期化を警告する."""
        raw = {
            "title": "statusCode 判定",
            "harness": "ワークフロー（GitHub Copilot harness）",
            "nodes": [
                _node(
                    "n1",
                    "workflow_trigger",
                    "手動実行",
                    [_p("トリガータイプ", "手動")],
                    [("n2", "")],
                ),
                _node(
                    "n2",
                    "workflow_action",
                    "Teams 投稿",
                    [
                        _p(
                            "コネクタとアクション",
                            "Microsoft Teams チャネルにメッセージを投稿",
                        ),
                        _p(
                            "入力パラメータ",
                            "件名、差出人、受信日時、メッセージID、本文抜粋",
                        ),
                        _p("設定（Settings）", "再試行ポリシー: 3回"),
                    ],
                    [("n3", "")],
                ),
                _node(
                    "n3",
                    "condition",
                    "statusCode 判定",
                    [
                        _p("左辺の変数", "statusCode"),
                        _p("演算子", "="),
                        _p("右辺の値", "200"),
                    ],
                    [("n4", "真: 成功"), ("n5", "偽: 失敗")],
                ),
                _end("n4", "成功"),
                _end("n5", "失敗"),
            ],
        }

        checks = validate_flow(normalize_result(raw))
        notification = next(
            check for check in checks if check.item == "通知の運用"
        )
        self.assertEqual(notification.status, "warn")
        self.assertIn("statusCode", notification.detail)
        self.assertIn("通知不要", notification.detail)


if __name__ == "__main__":
    unittest.main()
