"""生成されたブロックダイアグラムを検証するロジック."""

import re
from collections import Counter, deque
from dataclasses import dataclass

from copilot_nodes import CATALOG_BY_KEY

TRIGGER_TYPES = {"topic_trigger", "flow_trigger", "workflow_trigger"}
CONDITION_TYPES = {"condition", "condition_group"}

# PDF の設定項目に基づく、各ノードで最低限必要なパラメータ数。
MIN_PARAMS = {
    "topic_trigger": 1,
    "flow_trigger": 1,
    "workflow_trigger": 1,
    "message": 1,
    "question": 3,
    "adaptive_card": 2,
    "condition": 3,
    "condition_group": 2,
    "set_variable": 2,
    "http_request": 2,
    "generative_answers": 1,
    "redirect": 1,
    "end_conversation": 0,
    "call_action": 2,
    "prompt_node": 1,
    "agent_node": 1,
    "copilot_node": 1,
    "classify_node": 3,
    "workflow_action": 2,
    "extract_node": 2,
    "request_info": 4,
}

# ノード種別ごとのハーネス。共通ノード（condition / condition_group /
# set_variable / end_conversation / agent_node）はハーネスを固定しないため含めない。
HARNESS_BY_TYPE = {
    "topic_trigger": "topic",
    "message": "topic",
    "question": "topic",
    "adaptive_card": "topic",
    "http_request": "topic",
    "generative_answers": "topic",
    "redirect": "topic",
    "call_action": "topic",
    "flow_trigger": "agent_flow",
    "prompt_node": "agent_flow",
    "workflow_trigger": "workflow",
    "copilot_node": "workflow",
    "classify_node": "workflow",
    "workflow_action": "workflow",
    "extract_node": "workflow",
    "request_info": "workflow",
}
HARNESS_LABELS = {
    "topic": "エージェント トピック（標準ハーネス）",
    "agent_flow": "エージェントフロー（標準ハーネス）",
    "workflow": "ワークフロー（GitHub Copilot harness）",
}

TRUE_LABEL_HINTS = (
    "真",
    "true",
    "はい",
    "yes",
    "条件を満たす",
    "該当",
    "承認",
)
FALSE_LABEL_HINTS = (
    "その他",
    "else",
    "false",
    "偽",
    "いいえ",
    "no",
    "条件を満たさない",
    "非該当",
    "却下",
    "差し戻し",
    "否認",
    "承認しない",
    "承認不可",
    "非承認",
)
@dataclass(frozen=True)
class CheckResult:
    category: str
    item: str
    status: str  # pass / warn / fail
    detail: str
    required: bool = True


def _node_label(node: dict) -> str:
    name = node.get("name") or node.get("type") or "不明"
    node_id = node.get("id") or "-"
    return f"{name} ({node_id})"


def _node_params_text(node: dict) -> str:
    """パラメータ名・値だけをまとめた検索用テキスト."""
    params = node.get("parameters")
    params = params if isinstance(params, list) else []
    return " ".join(
        f"{p.get('name', '')} {p.get('value', '')}"
        for p in params
        if isinstance(p, dict)
    )


def _node_text(node: dict) -> str:
    """パラメータ名・値・指示プロンプトをまとめた検索用テキスト."""
    return _node_params_text(node) + " " + str(node.get("prompt") or "")


def _outgoing_edges(edges: list) -> dict:
    outgoing = {}
    for edge in edges:
        outgoing.setdefault(edge.get("from"), []).append(edge)
    return outgoing


def _upstream_ids(node_id: str, incoming: dict) -> set:
    visited = set()
    queue = deque([node_id])
    while queue:
        current = queue.popleft()
        for previous in incoming.get(current, []):
            if previous not in visited:
                visited.add(previous)
                queue.append(previous)
    return visited


def _find_cycles(nodes: list, edges: list) -> list:
    adjacency = {n.get("id"): [] for n in nodes if n.get("id")}
    for edge in edges:
        source = edge.get("from")
        target = edge.get("to")
        if source in adjacency and target in adjacency:
            adjacency[source].append(target)

    color = {node_id: 0 for node_id in adjacency}
    stack = []
    cycles = []

    def dfs(node_id: str) -> None:
        color[node_id] = 1
        stack.append(node_id)
        for next_id in adjacency[node_id]:
            if color[next_id] == 0:
                dfs(next_id)
            elif color[next_id] == 1:
                start = stack.index(next_id)
                cycle = stack[start:] + [next_id]
                if cycle not in cycles and list(reversed(cycle)) not in cycles:
                    cycles.append(cycle)
        stack.pop()
        color[node_id] = 2

    for node_id in adjacency:
        if color[node_id] == 0:
            dfs(node_id)
    return cycles


def _contains_marker(text: str, markers: tuple) -> bool:
    for marker in markers:
        if marker.isascii():
            if re.search(
                rf"(?<![a-z]){re.escape(marker)}(?![a-z])",
                text,
            ):
                return True
        elif marker in text:
            return True
    return False


def _branch_label_kind(label) -> str | None:
    """分岐ラベルを true / false / 不明に分類する."""
    text = str(label or "").strip().lower()
    if not text:
        return None
    if any(
        neutral in text
        for neutral in ("真偽", "承認待ち", "保留", "確認中")
    ):
        return None
    if _contains_marker(text, FALSE_LABEL_HINTS):
        return "false"
    if _contains_marker(text, TRUE_LABEL_HINTS):
        return "true"
    return None


def validate_flow(data: dict) -> list:
    """フロー全体を検証し、チェック結果の一覧を返す."""
    nodes = data.get("nodes") if isinstance(data, dict) else None
    edges = data.get("edges") if isinstance(data, dict) else None
    nodes = [n for n in nodes if isinstance(n, dict)] if isinstance(nodes, list) else []
    edges = [e for e in edges if isinstance(e, dict)] if isinstance(edges, list) else []

    checks = []

    # ------------------------------------------------------------ 構造
    if len(nodes) >= 2:
        checks.append(
            CheckResult("構造", "ノード数", "pass", f"{len(nodes)} 件のノードがあります。")
        )
    else:
        checks.append(
            CheckResult(
                "構造",
                "ノード数",
                "fail",
                "フローには2件以上のノードが必要です。",
            )
        )

    node_ids = [n.get("id") for n in nodes if n.get("id")]
    if len(node_ids) == len(set(node_ids)):
        checks.append(
            CheckResult("構造", "ノードIDの一意性", "pass", "ノードIDは一意です。")
        )
    else:
        checks.append(
            CheckResult("構造", "ノードIDの一意性", "fail", "重複したノードIDがあります。")
        )

    unknown_types = [
        str(n.get("type") or "")
        for n in nodes
        if n.get("type") not in CATALOG_BY_KEY
    ]
    if unknown_types:
        checks.append(
            CheckResult(
                "構造",
                "PDF記載のノード種別",
                "fail",
                "未定義の type: " + ", ".join(unknown_types),
            )
        )
    else:
        checks.append(
            CheckResult(
                "構造",
                "PDF記載のノード種別",
                "pass",
                "すべてのノードが PDF 記載の type です。",
            )
        )

    triggers = [n for n in nodes if n.get("type") in TRIGGER_TYPES]
    if len(triggers) == 1:
        checks.append(
            CheckResult(
                "構造",
                "トリガー",
                "pass",
                f"トリガー: {_node_label(triggers[0])}",
            )
        )
    elif not triggers:
        checks.append(
            CheckResult(
                "構造",
                "トリガー",
                "fail",
                "トリガー（topic_trigger / flow_trigger）がありません。",
            )
        )
    else:
        checks.append(
            CheckResult(
                "構造",
                "トリガー",
                "warn",
                f"トリガーが {len(triggers)} 件あります。開始点が意図どおりか確認してください。",
                required=False,
            )
        )

    harnesses = {
        HARNESS_BY_TYPE[n.get("type")]
        for n in nodes
        if n.get("type") in HARNESS_BY_TYPE
    }
    has_agent_node = any(n.get("type") == "agent_node" for n in nodes)
    if len(harnesses) > 1:
        labels = ", ".join(
            HARNESS_LABELS[h] for h in sorted(harnesses)
        )
        checks.append(
            CheckResult(
                "構造",
                "ハーネス混在",
                "fail",
                "1つのフローに異なるハーネスのノードが混在しています: "
                + labels,
            )
        )
    elif has_agent_node and harnesses == {"topic"}:
        checks.append(
            CheckResult(
                "構造",
                "ハーネス混在",
                "fail",
                "エージェントノードはエージェントフロー／ワークフロー向けです。"
                "エージェント トピックのノードとは混在できません。",
            )
        )
    elif len(harnesses) == 1:
        checks.append(
            CheckResult(
                "構造",
                "ハーネス混在",
                "pass",
                f"ハーネス: {HARNESS_LABELS[next(iter(harnesses))]}",
            )
        )
    else:
        checks.append(
            CheckResult(
                "構造",
                "ハーネス混在",
                "pass",
                "ハーネス固有ノードがないため、混在はありません。",
            )
        )

    if edges:
        checks.append(
            CheckResult("構造", "接続", "pass", f"{len(edges)} 本の接続があります。")
        )
    else:
        checks.append(
            CheckResult("構造", "接続", "fail", "ノード間の接続がありません。")
        )

    valid_ids = set(node_ids)
    in_degree = Counter(e.get("to") for e in edges)
    out_degree = Counter(e.get("from") for e in edges)
    invalid_edges = [
        e
        for e in edges
        if e.get("from") not in valid_ids or e.get("to") not in valid_ids
    ]
    if invalid_edges:
        details = ", ".join(
            f"{e.get('from')} -> {e.get('to')}" for e in invalid_edges[:5]
        )
        checks.append(
            CheckResult(
                "構造",
                "接続先の実在",
                "fail",
                f"存在しないノードへの接続: {details}",
            )
        )
    else:
        checks.append(
            CheckResult(
                "構造",
                "接続先の実在",
                "pass",
                "すべての接続先が実在します。",
            )
        )

    if not triggers:
        checks.append(
            CheckResult(
                "構造",
                "到達性",
                "warn",
                "トリガーがないため到達性を判定できません。",
                required=False,
            )
        )
    else:
        outgoing = _outgoing_edges(edges)
        visited = set()
        queue = deque(n["id"] for n in triggers if n.get("id"))
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for edge in outgoing.get(current, []):
                target = edge.get("to")
                if target in valid_ids and target not in visited:
                    queue.append(target)

        unreachable = [n for n in nodes if n.get("id") not in visited]
        if unreachable:
            checks.append(
                CheckResult(
                    "構造",
                    "到達性",
                    "fail",
                    "トリガーから到達できないノード: "
                    + ", ".join(_node_label(n) for n in unreachable),
                )
            )
        else:
            checks.append(
                CheckResult(
                    "構造",
                    "到達性",
                    "pass",
                    "すべてのノードがトリガーから到達可能です。",
                )
            )

    isolated_nodes = [
        n
        for n in nodes
        if in_degree.get(n.get("id"), 0) == 0
        and out_degree.get(n.get("id"), 0) == 0
        and n.get("type") not in TRIGGER_TYPES
    ]
    if isolated_nodes:
        checks.append(
            CheckResult(
                "構造",
                "孤立ノード",
                "fail",
                "孤立ノード: "
                + ", ".join(_node_label(n) for n in isolated_nodes),
            )
        )
    else:
        checks.append(
            CheckResult("構造", "孤立ノード", "pass", "孤立ノードはありません。")
        )

    if triggers:
        extra_starts = [
            n
            for n in nodes
            if in_degree.get(n.get("id"), 0) == 0
            and out_degree.get(n.get("id"), 0) > 0
            and n.get("type") not in TRIGGER_TYPES
        ]
        if extra_starts:
            checks.append(
                CheckResult(
                    "構造",
                    "トリガー以外の開始点",
                    "fail",
                    "トリガー以外から始まるノード: "
                    + ", ".join(_node_label(n) for n in extra_starts),
                )
            )
        else:
            checks.append(
                CheckResult(
                    "構造",
                    "トリガー以外の開始点",
                    "pass",
                    "トリガー以外の開始点はありません。",
                )
            )

    terminal_nodes = [n for n in nodes if out_degree.get(n.get("id"), 0) == 0]
    has_end_node = any(n.get("type") == "end_conversation" for n in nodes)
    if has_end_node:
        checks.append(
            CheckResult("構造", "終了処理", "pass", "終了ノードがあります。")
        )
    elif terminal_nodes:
        checks.append(
            CheckResult(
                "構造",
                "終了処理",
                "pass",
                "終端ノード: " + ", ".join(_node_label(n) for n in terminal_nodes),
            )
        )
    else:
        checks.append(
            CheckResult(
                "構造",
                "終了処理",
                "fail",
                "終了ノードも終端ノードもありません。フローが循環している可能性があります。",
            )
        )

    # ------------------------------------------------------------ パラメータ
    param_count_issues = []
    param_value_issues = []
    for node in nodes:
        minimum = MIN_PARAMS.get(node.get("type"), 0)
        if minimum == 0:
            continue
        params = node.get("parameters")
        params = params if isinstance(params, list) else []
        count_short = len(params) < minimum
        if count_short:
            param_count_issues.append(
                f"{_node_label(node)}: {len(params)}/{minimum}"
            )
        filled = sum(
            1
            for p in params
            if isinstance(p, dict) and str(p.get("value") or "").strip()
        )
        if not count_short and filled < minimum:
            param_value_issues.append(
                f"{_node_label(node)}: {filled}/{minimum}"
            )

    if param_count_issues:
        checks.append(
            CheckResult(
                "パラメータ",
                "パラメータ項目数",
                "fail",
                "項目が不足: " + "; ".join(param_count_issues),
            )
        )
    else:
        checks.append(
            CheckResult(
                "パラメータ",
                "パラメータ項目数",
                "pass",
                "各ノードに必要な数のパラメータ項目があります。",
            )
        )

    if param_value_issues:
        checks.append(
            CheckResult(
                "パラメータ",
                "パラメータ値",
                "fail",
                "値が不足: " + "; ".join(param_value_issues),
            )
        )
    else:
        checks.append(
            CheckResult(
                "パラメータ",
                "パラメータ値",
                "pass",
                "各ノードに必要な数のパラメータ値があります。",
            )
        )

    # ------------------------------------------------------------ 分岐
    outgoing = _outgoing_edges(edges)

    condition_nodes = [n for n in nodes if n.get("type") in CONDITION_TYPES]
    if condition_nodes:
        condition_issues = []
        condition_label_warnings = []
        for node in condition_nodes:
            branches = outgoing.get(node.get("id"), [])
            if len(branches) < 2:
                condition_issues.append(
                    f"{_node_label(node)}: {len(branches)} 本"
                )
                continue
            labels = [e.get("label") for e in branches]
            kinds = {_branch_label_kind(label) for label in labels}
            if not ("true" in kinds and "false" in kinds):
                condition_label_warnings.append(
                    f"{_node_label(node)}: 真偽ラベルを確認"
                )

        if condition_issues:
            checks.append(
                CheckResult(
                    "分岐",
                    "条件分岐の本数",
                    "fail",
                    "分岐が不足: " + "; ".join(condition_issues),
                )
            )
        else:
            checks.append(
                CheckResult(
                    "分岐",
                    "条件分岐の本数",
                    "pass",
                    "条件ノードに2本以上の分岐があります。",
                )
            )

        if condition_label_warnings:
            checks.append(
                CheckResult(
                    "分岐",
                    "条件分岐のラベル",
                    "warn",
                    "; ".join(condition_label_warnings),
                    required=False,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "分岐",
                    "条件分岐のラベル",
                    "pass",
                    "条件分岐に真偽を示すラベルがあります。",
                )
            )

    classify_nodes = [n for n in nodes if n.get("type") == "classify_node"]
    if classify_nodes:
        classify_issues = []
        classify_label_warnings = []
        for node in classify_nodes:
            branches = outgoing.get(node.get("id"), [])
            if len(branches) < 2:
                classify_issues.append(
                    f"{_node_label(node)}: {len(branches)} 本"
                )
                continue
            labels = [
                str(e.get("label") or "").strip()
                for e in branches
            ]
            if any(not label for label in labels):
                classify_label_warnings.append(
                    f"{_node_label(node)}: 空の分岐ラベルがあります"
                )
            joined_labels = " ".join(labels)
            if "苦情" in joined_labels:
                missing = [
                    category
                    for category in ("問い合わせ", "営業", "要確認")
                    if category not in joined_labels
                ]
                if missing:
                    classify_label_warnings.append(
                        f"{_node_label(node)}: カテゴリ分岐が不足"
                        f"（{', '.join(missing)}）"
                    )

        if classify_issues:
            checks.append(
                CheckResult(
                    "分岐",
                    "分類ノードの分岐",
                    "fail",
                    "分類分岐が不足: " + "; ".join(classify_issues),
                )
            )
        else:
            checks.append(
                CheckResult(
                    "分岐",
                    "分類ノードの分岐",
                    "pass",
                    "分類ノードに2本以上の分岐があります。",
                )
            )

        if classify_label_warnings:
            checks.append(
                CheckResult(
                    "分岐",
                    "分類カテゴリの分岐",
                    "warn",
                    "; ".join(classify_label_warnings),
                    required=False,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "分岐",
                    "分類カテゴリの分岐",
                    "pass",
                    "分類カテゴリごとの分岐ラベルがあります。",
                )
            )

    # ------------------------------------------------------------ メール分類・通知
    classify_nodes = [
        n for n in nodes if n.get("type") == "classify_node"
    ]
    agent_nodes = [n for n in nodes if n.get("type") == "agent_node"]
    workflow_actions = [
        n for n in nodes if n.get("type") == "workflow_action"
    ]
    workflow_triggers = [
        n for n in nodes if n.get("type") == "workflow_trigger"
    ]

    if classify_nodes:
        classify_param_warnings = []
        classify_rule_warnings = []
        for node in classify_nodes:
            params = node.get("parameters")
            params = params if isinstance(params, list) else []
            names = [
                str(p.get("name") or "")
                for p in params
                if isinstance(p, dict)
            ]
            values = [
                str(p.get("value") or "")
                for p in params
                if isinstance(p, dict)
            ]
            text = " ".join(names + values)
            if any("分岐先" in name for name in names):
                classify_param_warnings.append(
                    f"{_node_label(node)}: 分岐先は設定項目ではなく"
                    "キャンバス上の接続"
                )
            if any(
                "デフォルト" in name or "default" in name.lower()
                for name in names
            ):
                classify_rule_warnings.append(
                    f"{_node_label(node)}: デフォルトカテゴリを設定せず、"
                    "根拠に基づく判定ルールでカテゴリを決める"
                )
            output_ok = any(
                ("出力" in name or "output" in name.lower())
                and (
                    "category" in value.lower()
                    or "カテゴリ" in value
                )
                for name, value in zip(names, values)
            )
            if not output_ok:
                classify_rule_warnings.append(
                    f"{_node_label(node)}: 出力変数 Category を明示"
                )
            input_ok = "分類用" in text or (
                "件名" in text and "本文" in text
            )
            if not input_ok:
                classify_rule_warnings.append(
                    f"{_node_label(node)}: 入力は前処理済みの分類用入力"
                    "（件名＋本文テキスト）を使う"
                )
            if not ("根拠" in text and "苦情" in text):
                classify_rule_warnings.append(
                    f"{_node_label(node)}: 判定ルールに「根拠が1つでもあれば"
                    "苦情、単なる質問は問い合わせ、売り込みは営業、"
                    "根拠がなければ要確認」を明記"
                )

        if classify_param_warnings:
            checks.append(
                CheckResult(
                    "分類",
                    "分類ノードの設定項目",
                    "warn",
                    "; ".join(classify_param_warnings),
                    required=False,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "分類",
                    "分類ノードの設定項目",
                    "pass",
                    "分岐先を設定項目として扱っていません。",
                )
            )

        if classify_rule_warnings:
            checks.append(
                CheckResult(
                    "分類",
                    "分類の判定ルール",
                    "warn",
                    "; ".join(classify_rule_warnings),
                    required=False,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "分類",
                    "分類の判定ルール",
                    "pass",
                    "デフォルトカテゴリを使わず、根拠に基づく判定ルールが"
                    "記述されています。",
                )
            )

    if agent_nodes:
        agent_posting_warnings = []
        for node in agent_nodes:
            params = node.get("parameters")
            params = params if isinstance(params, list) else []
            text = " ".join(
                f"{p.get('name', '')} {p.get('value', '')}"
                for p in params
                if isinstance(p, dict)
            )
            text += " " + str(node.get("prompt") or "")
            posting_terms = (
                "投稿する",
                "投稿を実行",
                "メッセージを投稿",
                "Teamsに投稿",
                "Teams に投稿",
            )
            if any(k in text for k in posting_terms) and not any(
                k in text for k in ("workflow_action", "任せない", "投稿しない")
            ):
                agent_posting_warnings.append(
                    f"{_node_label(node)}: 投稿は workflow_action で固定し、"
                    "エージェントは要約・分類に限定"
                )

        if agent_posting_warnings:
            checks.append(
                CheckResult(
                    "通知",
                    "エージェントによる投稿",
                    "warn",
                    "; ".join(agent_posting_warnings),
                    required=False,
                )
            )
        elif workflow_actions:
            checks.append(
                CheckResult(
                    "通知",
                    "エージェントによる投稿",
                    "pass",
                    "投稿は workflow_action に分離されています。",
                )
            )

    if workflow_triggers:
        email_filter_warnings = []
        email_trigger_count = 0
        condition_nodes = [
            n for n in nodes if n.get("type") in CONDITION_TYPES
        ]
        condition_text = " ".join(
            f"{p.get('name', '')} {p.get('value', '')}"
            for condition_node in condition_nodes
            for p in (
                condition_node.get("parameters")
                if isinstance(condition_node.get("parameters"), list)
                else []
            )
            if isinstance(p, dict)
        )
        condition_text += " " + " ".join(
            str(n.get("prompt") or "") for n in condition_nodes
        )
        has_exclusion_node = any(
            key in condition_text
            for key in (
                "自動返信",
                "Auto-Reply",
                "配信停止",
                "unsubscribe",
                "除外",
            )
        )
        for node in workflow_triggers:
            params = node.get("parameters")
            params = params if isinstance(params, list) else []
            text = " ".join(
                f"{p.get('name', '')} {p.get('value', '')}"
                for p in params
                if isinstance(p, dict)
            )
            text += " " + str(node.get("prompt") or "")
            is_email = (
                "メール" in text
                or "Outlook" in text
                or "mail" in text.lower()
            )
            if not is_email:
                continue
            email_trigger_count += 1
            attachment_terms = (
                "添付ファイルを含める",
                "添付ファイルがある場合のみ",
                "添付なし",
                "PDFのみ",
                "PDF のみ",
            )
            if any(term in text for term in attachment_terms):
                email_filter_warnings.append(
                    f"{_node_label(node)}: トリガーに添付条件を設定しない。"
                    "本文分類だけなら添付条件は不要"
                )
            if not has_exclusion_node:
                email_filter_warnings.append(
                    f"{_node_label(node)}: 自動返信・配信停止などの除外条件を"
                    "独立した condition / condition_group で設計"
                )

        if email_trigger_count:
            if email_filter_warnings:
                checks.append(
                    CheckResult(
                        "通知",
                        "受信メールの除外条件",
                        "warn",
                        "; ".join(email_filter_warnings),
                        required=False,
                    )
                )
            else:
                checks.append(
                    CheckResult(
                        "通知",
                        "受信メールの除外条件",
                        "pass",
                        "トリガーに添付条件を置かず、除外条件を独立ノードで"
                        "設計しています。",
                    )
                )

    teams_actions = [
        n
        for n in workflow_actions
        if "Teams" in _node_params_text(n)
        and any(k in _node_params_text(n) for k in ("投稿", "メッセージ"))
        and "Outlook" not in _node_params_text(n)
        and "メールの送信" not in _node_params_text(n)
    ]
    alternative_actions = [
        n
        for n in workflow_actions
        if "Outlook" in _node_params_text(n)
        and "メール" in _node_params_text(n)
        and any(k in _node_params_text(n) for k in ("送信", "代替通知"))
    ]
    duplicate_nodes = [
        n
        for n in workflow_actions
        if "SharePoint" in _node_params_text(n)
        and any(k in _node_params_text(n) for k in ("取得", "検索"))
        and (
            "メッセージ" in _node_params_text(n)
            or "MessageID" in _node_params_text(n)
        )
        and "ID" in _node_params_text(n)
    ]
    log_nodes = [
        n
        for n in workflow_actions
        if "SharePoint" in _node_params_text(n)
        and any(
            k in _node_params_text(n)
            for k in ("項目の作成", "レコードの作成")
        )
        and not any(
            k in _node_params_text(n)
            for k in ("項目の更新", "レコードの更新")
        )
        and any(
            k in _node_params_text(n)
            for k in ("通知状態", "分類", "メッセージ")
        )
    ]
    condition_texts = [
        _node_text(n) for n in nodes if n.get("type") in CONDITION_TYPES
    ]
    has_duplicate_condition = any(
        any(k in text for k in ("重複", "件数", "exists", "1件以上"))
        for text in condition_texts
    )
    status_code_conditions = [
        n
        for n in nodes
        if n.get("type") in CONDITION_TYPES
        and any(
            k in _node_text(n)
            for k in ("statusCode", "StatusCode", "status code", "成功フラグ", "200")
        )
    ]
    set_variable_nodes = [
        n for n in nodes if n.get("type") == "set_variable"
    ]
    status_initialized = any(
        (
            "通知状態" in _node_params_text(n)
            or "NotificationStatus" in _node_params_text(n)
        )
        and any(
            k in _node_params_text(n)
            for k in ("通知不要", "初期化")
        )
        for n in set_variable_nodes
    )
    teams_has_try = any(
        "Try" in _node_params_text(n)
        and any(
            k in _node_params_text(n)
            for k in ("スコープ", "Scope")
        )
        for n in teams_actions
    )
    catch_actions = [
        n
        for n in alternative_actions
        if "Catch" in _node_params_text(n)
        and any(
            k in _node_params_text(n)
            for k in ("失敗", "タイムアウト", "Run after")
        )
    ]
    final_updates = [
        n
        for n in workflow_actions
        if "項目の更新" in _node_params_text(n)
        and any(
            k in _node_params_text(n)
            for k in ("Try 成功", "Catch 成功", "Try/Catch", "両方")
        )
    ]

    notification_warnings = []
    for node in teams_actions:
        text = _node_text(node)
        params_text = _node_params_text(node)
        if any(k in text for k in ("投稿ID", "成功フラグ")) and not any(
            k in text for k in ("使わない", "返さない", "なし", "不要", "前提にしない")
        ):
            notification_warnings.append(
                f"{_node_label(node)}: Teams 投稿は投稿IDや成功フラグを返さない。"
                "通知状態は後続の変数設定・項目更新で管理"
            )
        if "二重通知防止" in text:
            notification_warnings.append(
                f"{_node_label(node)}: 二重通知防止は Teams のパラメータではなく、"
                "SharePoint 検索＋条件の独立ノードで行う"
            )
        has_retry_setting = any(
            isinstance(p, dict)
            and (
                "設定" in str(p.get("name") or "")
                or "settings" in str(p.get("name") or "").lower()
            )
            and (
                "再試行" in str(p.get("name") or "")
                or "再試行" in str(p.get("value") or "")
                or "retry" in str(p.get("value") or "").lower()
            )
            for p in (
                node.get("parameters")
                if isinstance(node.get("parameters"), list)
                else []
            )
        )
        if not has_retry_setting:
            notification_warnings.append(
                f"{_node_label(node)}: 再試行はアクションの設定（Settings）に"
                "記述する"
            )
        teams_format_keys = ["件名", "差出人", "受信日時", "本文抜粋"]
        missing_format = [
            key for key in teams_format_keys if key not in params_text
        ]
        if not (
            "メッセージID" in params_text
            or "MessageID" in params_text
        ):
            missing_format.append("メッセージID")
        if missing_format:
            notification_warnings.append(
                f"{_node_label(node)}: Teams 投稿の固定フォーマットに"
                f"{', '.join(missing_format)} を追加"
            )

    if teams_actions:
        if not duplicate_nodes or not has_duplicate_condition:
            notification_warnings.append(
                "重複チェック: SharePoint「項目の取得」で内部名 MessageID を検索し、"
                "condition で1件以上なら終了する独立ノードを追加"
            )
        for node in duplicate_nodes:
            params_text = _node_params_text(node)
            if "メッセージID" in params_text and "MessageID" not in params_text:
                notification_warnings.append(
                    f"{_node_label(node)}: SharePoint のフィルターは表示名"
                    "「メッセージID」ではなく内部名 MessageID を使う"
                )
        if not alternative_actions:
            notification_warnings.append(
                "代替通知: Outlook「メールの送信」を独立した workflow_action で追加"
            )
        if not teams_has_try:
            notification_warnings.append(
                "Teams 投稿を Try スコープに入れ、実行条件（Run after）を設定する"
            )
        if not catch_actions:
            notification_warnings.append(
                "Catch: Teams 投稿が失敗／タイムアウトした時のみ実行する"
                "Outlook 代替通知を追加"
            )
        if not final_updates:
            notification_warnings.append(
                "最後の SharePoint「項目の更新」は Try 成功または Catch 成功後に"
                "実行する"
            )
        if not status_initialized:
            notification_warnings.append(
                "通知状態を分岐前に set_variable で「通知不要」に初期化する"
            )
        if status_code_conditions:
            notification_warnings.append(
                "statusCode／成功フラグによる成否判定は、Teams 投稿失敗時に"
                "後続が実行されないため使わない。Try/Catch の Run after を使う"
            )
        sharepoint_actions = [
            n
            for n in workflow_actions
            if "SharePoint" in _node_params_text(n)
        ]
        for node in sharepoint_actions:
            params_text = _node_params_text(node)
            if "サイト" not in params_text or "リスト" not in params_text:
                notification_warnings.append(
                    f"{_node_label(node)}: SharePoint のサイト名・リスト名を"
                    "取得／作成／更新で統一して明記"
                )
        if notification_warnings:
            checks.append(
                CheckResult(
                    "通知",
                    "通知の運用",
                    "warn",
                    "; ".join(notification_warnings),
                    required=False,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "通知",
                    "通知の運用",
                    "pass",
                    "重複チェック・再試行設定・Try/Catch・代替通知・"
                    "成否後の更新が独立ノード／設定として設計されています。",
                )
            )

    if classify_nodes and workflow_triggers:
        log_warnings = []
        if not log_nodes:
            log_warnings.append(
                "分類の前に、SharePoint「項目の作成」で受信日時・差出人・"
                "件名・分類ラベル・メッセージID・通知状態を記録する"
                "ログ作成ノードを1回だけ追加"
            )
        else:
            for node in log_nodes:
                params_text = _node_params_text(node)
                if "Title" not in params_text:
                    log_warnings.append(
                        f"{_node_label(node)}: SharePoint の Title＝件名を追加"
                    )
                if "受信日時" not in params_text or "差出人" not in params_text:
                    log_warnings.append(
                        f"{_node_label(node)}: 受信日時・差出人をログ項目に追加"
                    )
        if log_warnings:
            checks.append(
                CheckResult(
                    "通知",
                    "ログ作成（全件共通）",
                    "warn",
                    "; ".join(log_warnings),
                    required=False,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "通知",
                    "ログ作成（全件共通）",
                    "pass",
                    "SharePoint の作成アクションが全件共通のログとして"
                    "配置されています。",
                )
            )

    # ------------------------------------------------------------ RFI・抽出
    request_info_nodes = [
        n for n in nodes if n.get("type") == "request_info"
    ]
    if request_info_nodes:
        rfi_name_issues = []
        rfi_name_warnings = []
        for node in request_info_nodes:
            params = node.get("parameters")
            params = params if isinstance(params, list) else []
            names = [
                str(p.get("name") or "").lower()
                for p in params
                if isinstance(p, dict)
            ]
            joined = " ".join(names)
            if "配属先" in joined:
                rfi_name_issues.append(
                    f"{_node_label(node)}: 「配属先」は"
                    "「担当者（Assignees）」に修正"
                )
            elif not any(
                "担当者" in name or "assignee" in name for name in names
            ):
                rfi_name_issues.append(
                    f"{_node_label(node)}: 担当者（Assignees）の項目がありません"
                )
            if not any(
                "メッセージ" in name or "message" in name for name in names
            ):
                rfi_name_issues.append(
                    f"{_node_label(node)}: メッセージの項目がありません"
                )
            if not any(
                "タイトル" in name or "title" in name for name in names
            ):
                rfi_name_warnings.append(
                    f"{_node_label(node)}: タイトルの項目を確認"
                )
            if not any(
                "入力" in name or "input" in name or "フィールド" in name
                for name in names
            ):
                rfi_name_warnings.append(
                    f"{_node_label(node)}: 入力フィールドの項目を確認"
                )

        if rfi_name_issues:
            checks.append(
                CheckResult(
                    "RFI",
                    "RFIの必須項目名",
                    "fail",
                    "; ".join(rfi_name_issues),
                )
            )
        else:
            checks.append(
                CheckResult(
                    "RFI",
                    "RFIの必須項目名",
                    "pass",
                    "タイトル・メッセージ・担当者（Assignees）・"
                    "入力フィールドの項目があります。",
                )
            )

        if rfi_name_warnings:
            checks.append(
                CheckResult(
                    "RFI",
                    "RFIの推奨項目名",
                    "warn",
                    "; ".join(rfi_name_warnings),
                    required=False,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "RFI",
                    "RFIの推奨項目名",
                    "pass",
                    "RFI の推奨項目名に問題はありません。",
                )
            )

        incoming = {}
        for edge in edges:
            incoming.setdefault(edge.get("to"), []).append(edge.get("from"))
        extract_ids = {
            n.get("id") for n in nodes if n.get("type") == "extract_node"
        }
        dynamic_issues = []
        dynamic_checked = 0
        for node in request_info_nodes:
            upstream = _upstream_ids(node.get("id"), incoming)
            if not (upstream & extract_ids):
                continue
            dynamic_checked += 1
            params = node.get("parameters")
            params = params if isinstance(params, list) else []
            message_values = [
                str(p.get("value") or "")
                for p in params
                if isinstance(p, dict)
                and (
                    "メッセージ" in str(p.get("name") or "")
                    or "message" in str(p.get("name") or "").lower()
                )
            ]
            if not any(
                re.search(r"\{\{[^{}]+\}\}", value)
                for value in message_values
            ):
                dynamic_issues.append(
                    f"{_node_label(node)}: メッセージ本文に "
                    "{{...}} 形式の動的コンテンツがありません"
                )

        if dynamic_checked:
            if dynamic_issues:
                checks.append(
                    CheckResult(
                        "RFI",
                        "抽出結果の動的コンテンツ",
                        "fail",
                        "; ".join(dynamic_issues),
                    )
                )
            else:
                checks.append(
                    CheckResult(
                        "RFI",
                        "抽出結果の動的コンテンツ",
                        "pass",
                        "RFI メッセージに抽出結果の動的コンテンツが"
                        "埋め込まれています。",
                    )
                )

        outgoing = _outgoing_edges(edges)
        approval_warnings = []
        for node in request_info_nodes:
            branches = outgoing.get(node.get("id"), [])
            if len(branches) < 2:
                approval_warnings.append(
                    f"{_node_label(node)}: 承認可否の分岐を追加"
                )
                continue
            labels = [e.get("label") for e in branches]
            kinds = {_branch_label_kind(label) for label in labels}
            if not ("true" in kinds and "false" in kinds):
                approval_warnings.append(
                    f"{_node_label(node)}: 承認可否のラベルを確認"
                )

        if approval_warnings:
            checks.append(
                CheckResult(
                    "RFI",
                    "承認後の分岐",
                    "warn",
                    "; ".join(approval_warnings),
                    required=False,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "RFI",
                    "承認後の分岐",
                    "pass",
                    "RFI 後の承認可否分岐があります。",
                )
            )

    extract_nodes = [
        n for n in nodes if n.get("type") == "extract_node"
    ]
    if extract_nodes:
        model_warnings = []
        field_warnings = []
        invoice_nodes = []
        for node in extract_nodes:
            params = node.get("parameters")
            params = params if isinstance(params, list) else []
            text = " ".join(
                f"{p.get('name', '')} {p.get('value', '')}"
                for p in params
                if isinstance(p, dict)
            )
            text += " " + str(node.get("prompt") or "")

            for param in params:
                if not isinstance(param, dict):
                    continue
                name = str(param.get("name") or "")
                value = str(param.get("value") or "")
                if "モデル" in name and (
                    "請求書" in value or "invoice" in value.lower()
                ):
                    model_warnings.append(
                        f"{_node_label(node)}: 請求書専用モデルではなく"
                        "出力フィールド定義で設定"
                    )

            if "請求書" in text or "invoice" in text.lower():
                invoice_nodes.append(node)
                missing = [
                    field
                    for field in ("請求書番号", "税額", "通貨")
                    if field not in text
                ]
                if missing:
                    field_warnings.append(
                        f"{_node_label(node)}: 抽出項目に "
                        + ", ".join(missing)
                        + " を追加"
                    )

        if model_warnings:
            checks.append(
                CheckResult(
                    "抽出",
                    "抽出モデルの扱い",
                    "warn",
                    "; ".join(model_warnings),
                    required=False,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "抽出",
                    "抽出モデルの扱い",
                    "pass",
                    "請求書専用の事前構築モデルには依存していません。",
                )
            )

        if invoice_nodes:
            if field_warnings:
                checks.append(
                    CheckResult(
                        "抽出",
                        "請求書の抽出項目",
                        "warn",
                        "; ".join(field_warnings),
                        required=False,
                    )
                )
            else:
                checks.append(
                    CheckResult(
                        "抽出",
                        "請求書の抽出項目",
                        "pass",
                        "請求書番号・税額・通貨を含む抽出項目があります。",
                    )
                )

    # ------------------------------------------------------------ プロンプト・ラベル
    prompt_nodes = [
        n
        for n in nodes
        if n.get("type") not in TRIGGER_TYPES
        and n.get("supports_prompt", True)
    ]
    empty_prompts = [
        _node_label(n)
        for n in prompt_nodes
        if not str(n.get("prompt") or "").strip()
    ]
    if empty_prompts:
        checks.append(
            CheckResult(
                "プロンプト",
                "指示プロンプト",
                "fail",
                "指示プロンプトが空: " + ", ".join(empty_prompts),
            )
        )
    else:
        checks.append(
            CheckResult(
                "プロンプト",
                "指示プロンプト",
                "pass",
                "指示プロンプトが必要なノードにプロンプトがあります。",
            )
        )

    fallback_prompts = [
        _node_label(n)
        for n in prompt_nodes
        if n.get("prompt_source") == "catalog"
    ]
    if fallback_prompts:
        checks.append(
            CheckResult(
                "プロンプト",
                "指示プロンプトの参考例",
                "warn",
                "LLM が prompt を返さず、カタログ例を使用: "
                + ", ".join(fallback_prompts),
                required=False,
            )
        )
    else:
        checks.append(
            CheckResult(
                "プロンプト",
                "指示プロンプトの参考例",
                "pass",
                "ノード固有の指示プロンプトがあります。",
            )
        )

    action_nodes = [
        n for n in nodes if n.get("type") == "workflow_action"
    ]
    if action_nodes:
        action_prompt_warnings = []
        seen_prompts = {}
        for node in action_nodes:
            prompt = str(node.get("prompt") or "").strip()
            seen_prompts.setdefault(prompt, []).append(node)
            params_text = _node_params_text(node)
            if "Teams" in prompt and "Teams" not in params_text:
                action_prompt_warnings.append(
                    f"{_node_label(node)}: Teams 投稿のプロンプトが"
                    "他アクションにコピーされている可能性"
                )
        for prompt, group in seen_prompts.items():
            if prompt and len(group) > 1:
                action_prompt_warnings.append(
                    "同一の指示プロンプト: "
                    + ", ".join(_node_label(n) for n in group)
                )
        if action_prompt_warnings:
            checks.append(
                CheckResult(
                    "プロンプト",
                    "アクションの指示プロンプト",
                    "warn",
                    "; ".join(action_prompt_warnings),
                    required=False,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "プロンプト",
                    "アクションの指示プロンプト",
                    "pass",
                    "アクションごとに個別の指示プロンプトがあります。",
                )
            )

    set_variable_nodes = [
        n for n in nodes if n.get("type") == "set_variable"
    ]
    if set_variable_nodes:
        expression_warnings = []
        for node in set_variable_nodes:
            text = _node_params_text(node)
            if "PlainText(" in text or " & " in text:
                expression_warnings.append(
                    f"{_node_label(node)}: Power Automate 式に統一"
                    "（concat / variables / char(10)）"
                )
            if "\\n" in text:
                expression_warnings.append(
                    f"{_node_label(node)}: 改行は char(10) に統一"
                )
        if expression_warnings:
            checks.append(
                CheckResult(
                    "パラメータ",
                    "式の統一",
                    "warn",
                    "; ".join(expression_warnings),
                    required=False,
                )
            )
        else:
            checks.append(
                CheckResult(
                    "パラメータ",
                    "式の統一",
                    "pass",
                    "Power Automate 式と char(10) に統一されています。",
                )
            )

    trigger_prompts = [
        _node_label(n)
        for n in nodes
        if n.get("type") in TRIGGER_TYPES
        and str(n.get("prompt") or "").strip()
    ]
    if trigger_prompts:
        checks.append(
            CheckResult(
                "プロンプト",
                "トリガーの指示プロンプト",
                "warn",
                "トリガーには指示プロンプトを設定しません: "
                + ", ".join(trigger_prompts),
                required=False,
            )
        )
    else:
        checks.append(
            CheckResult(
                "プロンプト",
                "トリガーの指示プロンプト",
                "pass",
                "トリガーには指示プロンプトが設定されていません。",
            )
        )

    empty_labels = [
        _node_label(n) for n in nodes if not str(n.get("label") or "").strip()
    ]
    if empty_labels:
        checks.append(
            CheckResult(
                "プロンプト",
                "処理概要ラベル",
                "warn",
                "処理概要が空: " + ", ".join(empty_labels),
                required=False,
            )
        )
    else:
        checks.append(
            CheckResult(
                "プロンプト",
                "処理概要ラベル",
                "pass",
                "すべてのノードに処理概要があります。",
            )
        )

    # ------------------------------------------------------------ その他
    edge_keys = [
        (e.get("from"), e.get("to"), str(e.get("label") or "")) for e in edges
    ]
    duplicates = [key for key, count in Counter(edge_keys).items() if count > 1]
    if duplicates:
        details = ", ".join(f"{s} -> {t}" for s, t, _ in duplicates[:5])
        checks.append(
            CheckResult(
                "その他",
                "重複接続",
                "warn",
                f"重複した接続: {details}",
                required=False,
            )
        )
    else:
        checks.append(
            CheckResult("その他", "重複接続", "pass", "重複した接続はありません。")
        )

    cycles = _find_cycles(nodes, edges)
    if cycles:
        details = "; ".join(" -> ".join(cycle) for cycle in cycles[:3])
        checks.append(
            CheckResult(
                "その他",
                "循環参照",
                "warn",
                f"循環を検出: {details}",
                required=False,
            )
        )
    else:
        checks.append(
            CheckResult("その他", "循環参照", "pass", "循環参照はありません。")
        )

    return checks


def summarize_checks(checks: list) -> dict:
    """チェック結果を集計する."""
    fail_count = sum(1 for c in checks if c.status == "fail")
    warn_count = sum(1 for c in checks if c.status == "warn")
    pass_count = sum(1 for c in checks if c.status == "pass")
    return {
        "passed": fail_count == 0,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "pass_count": pass_count,
        "total": len(checks),
    }
