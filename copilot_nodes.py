"""Copilot Studio Flow で使用できるノード定義カタログ.

参照元:
- Microsoft Learn: https://learn.microsoft.com/ja-jp/microsoft-copilot-studio/
- ローカル参照: microsoft-copilot-studio.pdf（GitHub には含めない）

このカタログは、上記ドキュメントに記載されているノード／ブロックだけを抽出して
定義したものである。
アプリはこの一覧に含まれる type だけを LLM に提示し、一覧に無いブロックを
生成させない。

各エントリの pdf_page は PyPDF2 の 0-based ページ番号。
"""

SOURCE_URL = "https://learn.microsoft.com/ja-jp/microsoft-copilot-studio/"

NODE_CATALOG = [
    # ------------------------------------------------------------
    # エージェント トピック（標準ハーネス）
    # ------------------------------------------------------------
    {
        "key": "topic_trigger",
        "name": "トリガー",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "トピックを開始する条件を定義する。トリガーフレーズ、受信メッセージ、イベント、別トピックからの呼び出しなどで起動する。",
        "parameters": [
            "トリガータイプ（ユーザーがフレーズを発話／エージェントが選択／メッセージ受信／イベント／会話の変更／リダイレクト など）",
            "トリガーフレーズ（例: 有給休暇, 休暇申請）",
            "説明（「エージェントが選択する」場合にトピックの用途を記述）",
            "優先順位／トリガー条件",
        ],
        "prompt_example": "（トリガーには指示プロンプトを設定しません。トリガーフレーズと説明のみ設定します）",
        "supports_prompt": False,
        "pdf_page": 759,
    },
    {
        "key": "message",
        "name": "メッセージ",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "エージェントからユーザーへメッセージを送信する。テキストに加えて画像・動画・クイック返信・カードなども含められる。",
        "parameters": [
            "テキスト（エージェントが送信する本文）",
            "メッセージバリエーション",
            "音声の上書き",
            "画像／動画／クイック返信／カード",
        ],
        "prompt_example": "注文完了時に「ご注文ありがとうございます。3営業日以内に発送します。」と表示する",
        "pdf_page": 764,
    },
    {
        "key": "question",
        "name": "質問",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "ユーザーに情報の入力を求め、応答を変数に格納する。複数選択の回答、事前構築済みエンティティ、カスタムエンティティに対応する。",
        "parameters": [
            "質問テキスト",
            "回答タイプ（複数選択／事前構築済みエンティティ／カスタムエンティティ）",
            "出力変数",
            "再プロンプト／中断設定",
        ],
        "prompt_example": "「お届け先の都道府県を教えてください」と尋ね、回答を Topic.State に保存する",
        "pdf_page": 772,
    },
    {
        "key": "adaptive_card",
        "name": "アダプティブ カード",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "アダプティブカードを表示し、送信ボタンや入力フィールドでユーザーから情報を収集して変数に格納する。",
        "parameters": [
            "カードJSON（スキーマバージョン1.6以下）",
            "送信ボタン",
            "入力フィールド",
            "出力変数",
        ],
        "prompt_example": "名前・メールアドレス・希望連絡時間を入力するカードを表示し、回答を変数に保存する",
        "pdf_page": 780,
    },
    {
        "key": "condition",
        "name": "条件",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "ある変数の値を別の変数または特定の値と比較し、真の場合と「その他のすべての条件」の2つに分岐する。",
        "parameters": [
            "左辺の変数",
            "演算子（=, <>, >, <, contains など）",
            "右辺の値または変数",
            "条件が真の場合の分岐先",
            "その他のすべての条件の分岐先",
        ],
        "prompt_example": "Topic.State が \"California\" なら追加送料を案内し、それ以外は標準価格を表示する",
        "pdf_page": 791,
    },
    {
        "key": "condition_group",
        "name": "条件グループ",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "1つのノードで複数の条件を作成・管理し、分岐を減らす。テーブルビューとグラフビューを切り替えられる。",
        "parameters": [
            "条件リスト（変数・演算子・値）",
            "条件の結合（AND／OR）",
            "条件ごとの分岐先",
        ],
        "prompt_example": "州が California / Washington / Oregon のいずれかなら追加配送料の案内へ分岐する",
        "pdf_page": 797,
    },
    {
        "key": "set_variable",
        "name": "変数値の設定",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "変数に値または Power Fx 数式の結果を設定する。",
        "parameters": [
            "変数名",
            "値または Power Fx 数式",
            "スコープ（トピック変数／グローバル変数）",
        ],
        "prompt_example": "ProductURL に製品カテゴリに対応するページURLを Power Fx 数式で設定する",
        "pdf_page": 669,
    },
    {
        "key": "http_request",
        "name": "HTTP 要求",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "外部の REST API を呼び出してデータを取得または操作する。GET / POST / PATCH / PUT / DELETE をサポートする。",
        "parameters": [
            "URL（APIエンドポイント）",
            "メソッド（GET／POST／PATCH／PUT／DELETE）",
            "ヘッダー／ボディ",
            "認証",
            "応答を格納する出力変数",
        ],
        "prompt_example": "GET https://api.example.com/stock/{Topic.ProductId} を呼び出し、結果を Stock 変数に保存する",
        "pdf_page": 888,
    },
    {
        "key": "generative_answers",
        "name": "生成型の回答",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "トピックレベルの知識ソースに基づいて回答を生成する。SharePoint、公開Webサイト、アップロードされたドキュメントなどをソースにできる。",
        "parameters": [
            "ナレッジソース（SharePoint／公開Webサイト／アップロード文書 など）",
            "検索クエリ／入力",
            "温度・モデル設定",
            "引用／参照の表示",
        ],
        "prompt_example": "社内FAQのSharePointサイトを検索して、返品条件について回答を生成する",
        "pdf_page": 855,
    },
    {
        "key": "redirect",
        "name": "別のトピックに移動",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "現在のトピックから別のトピックへ会話をリダイレクトする。",
        "parameters": [
            "移動先トピック",
            "渡す入力変数",
            "移動先トリガーの非アクティブ期間（必要時）",
        ],
        "prompt_example": "会話を「メインメニュー」トピックへ移動する",
        "pdf_page": 1444,
    },
    {
        "key": "end_conversation",
        "name": "会話の終了",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "会話を終了する。終了メッセージや通話後アクションを設定できる。",
        "parameters": [
            "終了メッセージ",
            "アンケート（必要時）",
            "通話後アクション（音声エージェントの場合）",
        ],
        "prompt_example": "「本日はありがとうございました」と表示して会話を終了する",
        "pdf_page": 744,
    },
    {
        "key": "call_action",
        "name": "アクションの呼び出し",
        "category": "エージェント トピック（標準ハーネス）",
        "description": "Power Automate のクラウドフローなど外部アクションを呼び出し、結果を変数に格納する。",
        "parameters": [
            "呼び出すクラウドフロー／コネクタ",
            "入力パラメータ",
            "出力変数",
        ],
        "prompt_example": "Power Automate の「休暇申請」フローを呼び出し、結果を ApprovalResult に保存する",
        "pdf_page": 1003,
    },
    # ------------------------------------------------------------
    # エージェントフロー（標準ハーネス）
    # ------------------------------------------------------------
    {
        "key": "flow_trigger",
        "name": "トリガー",
        "category": "エージェントフロー（標準ハーネス）",
        "description": "エージェントフローを開始するイベント。即時（手動・オンデマンド実行）、スケジュール、または他のイベントによる起動がある。トリガー出力の項目は接続するコネクタ側で決まる。",
        "parameters": [
            "トリガータイプ（手動／スケジュール／イベント）",
            "スケジュール設定（スケジュール実行の場合のみ）",
            "コネクタとイベント（イベント駆動の場合）",
            "コネクタのトリガー出力（ファイル識別子、メール添付ファイルなど。出力項目はコネクタ側で決まる）",
        ],
        "prompt_example": "（トリガーには指示プロンプトを設定しません。SharePoint のファイル作成やメール受信などのトリガー条件のみ設定します）",
        "supports_prompt": False,
        "pdf_page": 2020,
    },
    {
        "key": "prompt_node",
        "name": "プロンプトノード",
        "category": "エージェントフロー（標準ハーネス）",
        "description": "エージェントフロー内から単一の AI 呼び出しを行い、テキストまたは構造化された出力を返す。",
        "parameters": [
            "プロンプト命令",
            "前のステップの動的コンテンツ",
            "モデル選択",
            "温度",
            "出力形式（テキスト／構造化出力）",
        ],
        "prompt_example": "メール本文を100文字以内に要約し、要約テキストを次のステップへ渡す",
        "pdf_page": 2036,
    },
    {
        "key": "agent_node",
        "name": "エージェントノード",
        "category": "ワークフロー（GitHub Copilot harness）",
        "description": "フローを AI エージェントに渡し、推論・ツール呼び出し・知識源からの検索を行わせて結果を返す。ワークフロー（GitHub Copilot harness）向け。エージェントフロー（標準ハーネス）でも利用可能（PDF p.2031）。利用するハーネスは1つに固定し、他のハーネスと混在させない。メール本文などの外部入力は信頼できないものとして扱い、要約や分類などに限定する。Teams 投稿などの固定処理はエージェントノードに任せず、workflow_action で行う。",
        "parameters": [
            "エージェント（既存の公開エージェント／インライン作成。画面の項目名に合わせる）",
            "自然言語の指示",
            "ツール（MCPサーバー／コネクタ）",
            "知識（SharePointサイト／公開Webサイト）",
            "後続ステップで使う応答",
        ],
        "prompt_example": "メール本文を要約し、分類ラベルを返す（Teams への投稿は workflow_action で行う）",
        "pdf_page": 1978,
    },
    # ------------------------------------------------------------
    # ワークフロー（GitHub Copilot harness）
    # ------------------------------------------------------------
    {
        "key": "workflow_trigger",
        "name": "トリガー",
        "category": "ワークフロー（GitHub Copilot harness）",
        "description": "ワークフローを開始するトリガー。コネクタのイベント、スケジュール、手動実行などを設定する。トリガー出力の項目は接続するコネクタ側で決まる。",
        "parameters": [
            "トリガータイプ（手動／スケジュール／イベント）",
            "コネクタとイベント（例: メール受信、SharePoint のファイル作成）",
            "スケジュール設定（スケジュール実行の場合のみ）",
            "コネクタのトリガー出力（ファイル識別子、メール添付ファイルなど）",
        ],
        "prompt_example": "（トリガーには指示プロンプトを設定しません。ワークフローのトリガー条件のみ設定します）",
        "supports_prompt": False,
        "pdf_page": 2010,
    },
    {
        "key": "copilot_node",
        "name": "Copilot ノード",
        "category": "ワークフロー（GitHub Copilot harness）",
        "description": "Copilot Chat や Cowork タスクを実行し、接続されたユーザーのメール・ファイル・カレンダー・チャットなどに基づいて回答・要約・下書き・タスク委任を行う。",
        "parameters": [
            "実行種別（Copilot Chat／Cowork）",
            "プロンプト／タスク指示",
            "対象エージェント（Researcher／Analyst／Agent Builder など）",
            "前のステップの動的コンテンツ",
            "後続ステップで使う応答",
        ],
        "prompt_example": "Copilot Chat で「このメールスレッドを要約して」と実行し、要約を次のステップへ渡す",
        "pdf_page": 1990,
    },
    {
        "key": "classify_node",
        "name": "分類ノード",
        "category": "ワークフロー（GitHub Copilot harness）",
        "description": "テキストを定義済みのカテゴリに AI で分類し、カテゴリごとに独立したブランチへ分岐する。分岐先は設定項目ではなく、キャンバス上で接続する。PDF p.1997 に記載。実画面に分類ノードがない場合は、エージェントノードで分類ラベルを出力して後続で分岐するか、抽出ノードで分類ラベルを取り出す代替を検討する。",
        "parameters": [
            "入力テキスト（件名と本文を結合するなど）",
            "カテゴリ名と説明",
            "カテゴリごとの入力例",
            "デフォルトカテゴリ（迷った場合は苦情寄り、または「要確認」カテゴリを用意）",
        ],
        "prompt_example": "メールの件名と本文を「苦情」「問い合わせ」「営業」「要確認」に分類し、苦情なら Teams 通知へ分岐する",
        "pdf_page": 1997,
    },
    {
        "key": "workflow_action",
        "name": "アクション",
        "category": "ワークフロー（GitHub Copilot harness）",
        "description": "Teams や Outlook などのコネクタアクションを実行する。投稿・通知・レコード作成など、AI に任せず固定の処理を行いたい場合に使う。投稿先やメッセージ形式を固定でき、成功／失敗はアクションの実行結果で判定できる。",
        "parameters": [
            "コネクタとアクション（例: Microsoft Teams の「チャネルにメッセージを投稿」）",
            "接続",
            "入力パラメータ（投稿先チーム／チャネル、メッセージ本文など）",
            "出力（成功／失敗、投稿 ID など）",
        ],
        "prompt_example": "Teams の指定チャネルに、エージェントノードが生成した要約を投稿する",
        "pdf_page": 2020,
    },
    {
        "key": "extract_node",
        "name": "抽出ノード",
        "category": "ワークフロー（GitHub Copilot harness）",
        "description": "PDF / Word / Excel / PowerPoint などのドキュメントを処理し、定義した名前付きの値やテーブルを抽出する。入力は動的コンテンツピッカーで前のトリガー・アクション・ノードから選択する。請求書専用の事前構築モデルを選ぶのではなく、出力フィールドを自分で定義する。",
        "parameters": [
            "入力ドキュメント（動的コンテンツピッカーで前のトリガー／アクション／ノードのファイルまたはファイル内容を選択）",
            "モデル選択（任意。請求書専用の事前構築モデルではない）",
            "出力フィールド（サンプルドキュメント／テンプレート／手動追加から定義）",
            "テーブルフィールド（明細行などの繰り返しデータ）",
            "テスト用ドキュメント（ノード内のテストパネルで抽出結果を確認）",
        ],
        "prompt_example": "請求書PDFから請求書番号・請求日・請求元・税額・通貨・合計金額・明細テーブルを抽出する",
        "pdf_page": 2002,
    },
    {
        "key": "request_info",
        "name": "要求情報（RFI）",
        "category": "ワークフロー（GitHub Copilot harness）",
        "description": "ワークフローを一時停止し、指定した人間の担当者から情報を収集してから実行を再開する。入力フィールドの値は後続アクションで動的コンテンツとして利用できる。メッセージ本文には、前の抽出ノードなどの出力を動的コンテンツとして埋め込む。承認／却下の判断自体は Approvals コネクタの承認アクションが一般的で、RFI は情報入力の要求に使う。",
        "parameters": [
            "タイトル",
            "メッセージ（抽出結果を動的コンテンツで埋め込む。例: 請求書番号・請求日・請求元・税額・通貨・合計金額・明細）",
            "担当者（Assignees。レビュー担当者のメールアドレス）",
            "入力フィールド（テキスト／はい・いいえ／メール／数値／日付。必須／任意、単一選択／複数選択、プレースホルダーを設定）",
            "入力フィールドの既定値（抽出結果を編集可能にする場合）",
        ],
        "prompt_example": "抽出結果（請求書番号・請求日・請求元・税額・通貨・合計金額・明細）をメッセージ本文に埋め込み、担当者（Assignees）に承認／修正の入力を要求する",
        "pdf_page": 2009,
    },
]

ALLOWED_KEYS = {node["key"] for node in NODE_CATALOG}
CATALOG_BY_KEY = {node["key"]: node for node in NODE_CATALOG}


def build_catalog_text() -> str:
    """LLM のシステムプロンプトに埋め込むカタログ文字列を生成する."""
    lines = []
    for node in NODE_CATALOG:
        params = "／".join(node["parameters"])
        if node.get("supports_prompt", True):
            prompt_line = f"  指示プロンプトの参考例: {node['prompt_example']}"
        else:
            prompt_line = (
                "  指示プロンプト: 設定しない"
                "（トリガーには指示プロンプトを設定しません）"
            )
        lines.append(
            f"- type: {node['key']}\n"
            f"  名前: {node['name']}\n"
            f"  カテゴリ: {node['category']}\n"
            f"  説明: {node['description']}\n"
            f"  指定すべきパラメータ: {params}\n"
            f"{prompt_line}"
        )
    return "\n".join(lines)
