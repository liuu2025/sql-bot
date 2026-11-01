"""Conversation replies and bounded date clarification, without executing guessed SQL."""

import json
import re
from datetime import date, datetime

from common.utils.locale import I18n

REPLY_KEY = "_conversation_reply"
_CN = {char: index for index, char in enumerate("零一二三四五六七八九")}


def _number(value):
    if value.isdigit():
        return int(value)
    if "十" in value:
        left, right = value.split("十", 1)
        return (_CN.get(left, 1) * 10) + _CN.get(right, 0)
    return _CN.get(value, 0)


def explicit_month(question, today=None):
    """Return an unambiguous month explicitly supplied by the user."""
    today = today or date.today()
    if re.search(r"(?:各|每|所有|全部|跨)个?月|所有月份|全部月份", question):
        return None
    matches = set()
    for match in re.finditer(
        r"(?:(20\d{2})\s*年\s*)?([0-9一二三四五六七八九十]{1,3})\s*月", question
    ):
        month = _number(match[2])
        if 1 <= month <= 12:
            matches.add((int(match[1]) if match[1] else today.year, month))
    for match in re.finditer(r"\b(20\d{2})-(0?[1-9]|1[0-2])(?:-\d{1,2})?\b", question):
        matches.add((int(match[1]), int(match[2])))
    for word, delta in (
        ("本月", 0),
        ("这个月", 0),
        ("上个月", -1),
        ("上月", -1),
        ("下个月", 1),
        ("下月", 1),
    ):
        if word in question:
            absolute = today.year * 12 + today.month - 1 + delta
            matches.add((absolute // 12, absolute % 12 + 1))
    return next(iter(matches)) if len(matches) == 1 else None


def day_request(question):
    if re.search(
        r"(?:过去|最近|近|未来|前|后)\s*[0-9一二三四五六七八九十]+\s*[日天]", question
    ):
        return None
    match = re.search(
        r"(?<![0-9一二三四五六七八九十第])([0-9一二三四五六七八九十]{1,3})\s*[号日]",
        question,
    )
    if not match:
        return None
    day = _number(match[1])
    return day if 1 <= day <= 31 else None


def month_is_supplied(question):
    return bool(
        re.search(
            r"(?:[0-9一二三四五六七八九十]{1,3})\s*月|20\d{2}-\d{1,2}|本月|这个月|上月|上个月|下月|下个月",
            question,
        )
    )


def missing_month(question, history=(), today=None):
    day = day_request(question)
    if not day or re.search(r"(?:各|每|所有|全部|跨)个?月|所有月份|全部月份", question):
        return None
    if month_is_supplied(question):
        return None
    if inherited_month(question, history, today):
        return None
    return day


def inherited_month(question, history=(), today=None):
    if not day_request(question) or month_is_supplied(question):
        return None
    if re.search(r"(?:各|每|所有|全部|跨)个?月|所有月份|全部月份", question):
        return None
    for previous in reversed(list(history)):
        value = explicit_month(previous, today)
        if value:
            return value
        if month_is_supplied(previous) or re.search(
            r"(?:各|每|所有|全部|跨)个?月|所有月份|全部月份", previous
        ):
            break
    return None


def read_reply(data):
    try:
        payload = json.loads(data) if isinstance(data, str) else data
        reply = payload.get(REPLY_KEY) if isinstance(payload, dict) else None
        return reply if isinstance(reply, dict) else None
    except (ValueError, TypeError):
        return None


def model_reply(payload):
    """Non-query actions take precedence even if a model also supplied SQL."""
    kind = payload.get("action")
    if kind not in (None, "query", "answer", "clarify"):
        raise ValueError("Unsupported conversation action")
    if kind not in ("answer", "clarify"):
        if payload.get("success") is not False:
            return None
        kind = "answer"  # Legacy refusal/explanation is a normal assistant message.
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Missing conversation message")
    options = []
    suggested = payload.get("options")
    for item in (suggested if isinstance(suggested, list) else [])[:12]:
        if isinstance(item, str):
            item = {"label": item, "question": item}
        if not isinstance(item, dict):
            continue
        label, question = item.get("label"), item.get("question")
        if (
            isinstance(label, str)
            and isinstance(question, str)
            and label.strip()
            and question.strip()
        ):
            options.append({"label": label[:100], "question": question[:1500]})
    return {
        "kind": kind,
        "message": message[:8000],
        "options": options if kind == "clarify" else [],
    }


def date_clarification(question, day, start=None, end=None):
    trans = I18n()(lang="zh-CN")
    options = []
    if start and end:
        first = start.year * 12 + start.month - 1
        last = end.year * 12 + end.month - 1
        # Bounded suggestions; other dates remain available through ordinary input.
        for absolute in range(max(first, last - 11), last + 1):
            year, month = absolute // 12, absolute % 12 + 1
            try:
                chosen = date(year, month, day)
            except ValueError:
                continue
            label = f"{year}年{month}月{day}日"
            options.append(
                {
                    "label": label,
                    "question": trans("i18n_conversation.date_choice").format(
                        question=question, date=chosen.isoformat()
                    ),
                }
            )
    options.append(
        {
            "label": trans("i18n_conversation.all_months").format(day=day),
            "question": trans("i18n_conversation.all_months_question").format(
                question=question, day=day
            ),
        }
    )
    message = trans("i18n_conversation.ask_month").format(day=day)
    if start and end:
        message += trans("i18n_conversation.date_range").format(
            start=start.isoformat(), end=end.isoformat()
        )
    return {"kind": "clarify", "message": message, "options": options}


def available_date_range(session, user, ds, policy, table_names=None):
    """Read MIN/MAX only for one allowed date field; never sample customer rows."""
    from sqlglot import exp

    from apps.datasource.models.datasource import CoreDatasource, CoreField, CoreTable
    from apps.datasource.query_policy import execute_query

    if not isinstance(ds, CoreDatasource):
        return None, None
    candidates = []
    tables = session.query(CoreTable).filter(CoreTable.ds_id == ds.id).all()
    for table in tables:
        if table_names is not None and table.table_name not in table_names:
            continue
        for column in (
            session.query(CoreField).filter(CoreField.table_id == table.id).all()
        ):
            if column.field_name not in policy.tables.get(table.table_name, ()):
                continue
            if re.search(r"date|timestamp", column.field_type or "", re.I):
                candidates.append((table.table_name, column.field_name))
    if len(candidates) != 1:
        return None, None
    table, column = candidates[0]
    sql = (
        exp.select(
            exp.Min(this=exp.column(column, quoted=True)).as_("first_date"),
            exp.Max(this=exp.column(column, quoted=True)).as_("last_date"),
        )
        .from_(exp.Table(this=exp.to_identifier(table, quoted=True)))
        .sql(dialect=policy.dialect)
    )
    result = execute_query(session, user, ds, sql)
    rows = result.get("data") or []
    if not rows:
        return None, None

    def as_date(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    return as_date(rows[0].get("first_date")), as_date(rows[0].get("last_date"))


def result_summary(record):
    """Carry small useful results forward without replaying whole customer rows."""
    try:
        payload = json.loads(record.data or "{}")
    except (ValueError, TypeError):
        return None
    rows = payload.get("data")
    if not isinstance(rows, list):
        return None
    summary = {"question": record.question, "returned_rows": len(rows)}
    if len(rows) == 1:
        numbers = {
            key: value
            for key, value in rows[0].items()
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and not re.search(
                r"phone|mobile|telephone|address|email|手机号|电话|姓名", key, re.I
            )
        }
        if numbers:
            summary["numeric_results"] = dict(list(numbers.items())[:10])
    for key in payload.get("fields", []):
        if re.search(r"^(?:order_(?:id|no|number)|订单号)$", key, re.I):
            summary["order_ids"] = [row[key] for row in rows[:5] if key in row]
        elif re.search(r"date|日期", key, re.I):
            values = [str(row[key])[:19] for row in rows if row.get(key)]
            if values:
                summary["returned_date_range"] = [min(values), max(values)]
    return summary
