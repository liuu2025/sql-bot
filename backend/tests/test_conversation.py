"""Offline contracts for conversation routing and meaningful date clarification."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from apps.chat.conversation import (
    REPLY_KEY,
    date_clarification,
    day_request,
    explicit_month,
    missing_month,
    model_reply,
    read_reply,
    result_summary,
)


@pytest.mark.parametrize(
    "question,expected",
    [
        ("查一下25号详情", 25),
        ("看看二十五号的订单", 25),
        ("查询十号", 10),
        ("统计订单数量", None),
        ("查前25条订单", None),
        ("过去25日销售额", None),
        ("订单号TEST-25", None),
        ("第25号订单", None),
        ("查询0号", None),
    ],
)
def test_day_detection_does_not_confuse_counts_with_dates(question, expected):
    assert day_request(question) == expected


def test_bare_day_requires_month_and_explicit_context_resolves_it():
    assert missing_month("25号详情") == 25
    assert missing_month("二十五号详情") == 25
    assert missing_month("25号详情", ["统计订单", "查询2026年9月订单"]) is None
    assert missing_month("25号详情", ["查一下25号详情"]) == 25
    assert missing_month("所有月份的25号") is None
    assert missing_month("本月25号") is None
    assert missing_month("2026年9月25号") is None
    assert missing_month("查询9月和10月25号") is None
    assert missing_month("25号", ["2026年9月", "2026年4月至6月"]) == 25


@pytest.mark.parametrize(
    "question,expected",
    [
        ("2026年九月订单", (2026, 9)),
        ("9月25号", (2026, 9)),
        ("2026-09-25", (2026, 9)),
        ("上个月25号", (2026, 9)),
        ("本月25号", (2026, 10)),
        ("所有月份的25号", None),
        ("9月和10月", None),
    ],
)
def test_explicit_month_understands_calendar_context(question, expected):
    assert explicit_month(question, date(2026, 10, 29)) == expected


def test_month_options_are_real_calendar_dates_with_original_intent():
    reply = date_clarification("查25号详情", 25, date(2026, 4, 1), date(2026, 9, 28))
    assert reply["kind"] == "clarify"
    assert len(reply["options"]) == 7
    assert reply["options"][0]["label"] == "2026年4月25日"
    assert "2026-09-25" in reply["options"][5]["question"]
    assert missing_month(reply["options"][5]["question"]) is None
    assert missing_month(reply["options"][-1]["question"]) is None
    assert "2026-04-01" in reply["message"] and "2026-09-28" in reply["message"]


def test_month_options_skip_impossible_days_and_are_bounded():
    reply = date_clarification("查31号", 31, date(2024, 1, 1), date(2026, 12, 31))
    assert len(reply["options"]) <= 13
    assert all("年2月31日" not in option["label"] for option in reply["options"])


@pytest.mark.parametrize("kind", ["answer", "clarify"])
def test_non_query_kind_wins_even_when_model_also_returns_sql(kind):
    reply = model_reply(
        {
            "success": True,
            "action": kind,
            "message": "请明确月份",
            "sql": "SELECT private_data FROM forbidden",
            "options": [{"label": "九月", "question": "查询2026年9月25号"}],
        }
    )
    assert reply["kind"] == kind and "sql" not in reply
    assert bool(reply["options"]) is (kind == "clarify")


def test_legacy_explanation_is_normal_reply_and_query_stays_query():
    assert (
        model_reply({"success": False, "message": "这是一张订单表"})["kind"] == "answer"
    )
    assert model_reply({"success": True, "sql": "SELECT COUNT(*) FROM orders"}) is None
    with pytest.raises(ValueError):
        model_reply({"action": "clarify", "message": ""})


def test_bad_option_shapes_are_not_rendered_as_buttons():
    reply = model_reply(
        {"action": "clarify", "message": "选择月份", "options": "不是列表"}
    )
    assert reply["options"] == []


def test_unknown_action_cannot_fall_back_to_sql_execution():
    with pytest.raises(ValueError, match="Unsupported conversation action"):
        model_reply({"success": True, "action": "unknown", "sql": "SELECT 1"})


def test_persisted_reply_roundtrip_and_small_safe_result_summary():
    reply = {"kind": "clarify", "message": "选择月份", "options": []}
    assert read_reply(json.dumps({REPLY_KEY: reply})) == reply
    assert read_reply("invalid json") is None
    record = SimpleNamespace(
        question="查订单",
        data=json.dumps(
            {
                "fields": ["order_no", "order_date", "phone", "address"],
                "data": [
                    {
                        "order_no": "TEST-1",
                        "order_date": "2026-09-25",
                        "phone": "synthetic-private",
                        "address": "synthetic-private",
                    }
                ],
            }
        ),
    )
    summary = result_summary(record)
    assert summary["order_ids"] == ["TEST-1"]
    assert summary["returned_date_range"] == ["2026-09-25", "2026-09-25"]
    assert "synthetic-private" not in json.dumps(summary)
