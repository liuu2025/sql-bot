"""Opt-in real PG task/HTTP checks; provider responses use synthetic fixtures."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessageChunk
from sqlalchemy import text
from sqlmodel import Session
from test_embedding_parameters_integration import knowledge_environment, pytestmark  # noqa: F401
from test_query_policy_integration import privacy_environment  # noqa: F401
from test_table_parameters_integration import table_environment, task  # noqa: F401

from apps.ai_model.model_factory import LLMConfig
from apps.chat.conversation import REPLY_KEY, read_reply
from apps.chat.models.chat_model import ChatFinishStep, ChatQuestion, ChatRecord
from apps.chat.task.llm import LLMService
from apps.datasource.models.datasource import CoreField, CoreTable


@pytest.fixture
def conversation_environment(privacy_environment):  # noqa: F811
    database, client, ds_id = privacy_environment
    with database.begin() as connection:
        connection.execute(text("ALTER TABLE sales_alpha ADD COLUMN created_at DATE"))
        connection.execute(
            text(
                "UPDATE sales_alpha SET created_at = CASE WHEN id = 1 THEN DATE '2026-09-25' ELSE DATE '2026-04-25' END"
            )
        )
    with Session(database) as session:
        table = (
            session.query(CoreTable).filter(CoreTable.table_name == "sales_alpha").one()
        )
        session.add(
            CoreField(
                ds_id=ds_id,
                table_id=table.id,
                field_name="created_at",
                field_type="DATE",
                field_index=6,
                checked=True,
            )
        )
        session.commit()
    yield database, client, ds_id


class Provider:
    def __init__(self, payload):
        self.payload = payload
        self.sql_contexts = []

    def stream(self, messages):
        context = "\n".join(message.content for message in messages)
        if "【Schema】" in context:
            self.sql_contexts.append(context)
            value = json.dumps(self.payload)
        else:
            value = "sales"
        yield AIMessageChunk(content=value)


def run(service, payload):
    service.llm = Provider(payload)
    results = list(
        service.run_task(
            in_chat=False, stream=False, finish_step=ChatFinishStep.QUERY_DATA
        )
    )
    assert results[-1]["success"], results
    return results[-1]


def followup(database, previous, question):
    with Session(database) as session:
        service = LLMService(
            session,
            SimpleNamespace(id=1, oid=1, language="zh-CN"),
            ChatQuestion(chat_id=previous.record.chat_id, question=question),
            config=LLMConfig(
                model_type="openai",
                model_name="test",
                api_key="test",
                api_base_url="http://127.0.0.1:9/v1",
            ),
        )
        service.init_record(session)
    return service


def test_bare_day_returns_persisted_buttons_without_generating_guessed_sql(
    conversation_environment,
):
    database, client, ds_id = conversation_environment
    service = task(database, ds_id, question="查一下25号的订单详情")
    final_query = Mock(side_effect=AssertionError("A guessed query must not execute"))
    service.execute_sql = final_query
    result = run(service, {"success": True, "sql": "SELECT phone FROM sales_alpha"})
    assert result["action"] == "clarify"
    reply = result["reply"]
    assert len(reply["options"]) == 7
    assert reply["options"][5]["label"] == "2026年9月25日"
    assert not service.llm.sql_contexts
    final_query.assert_not_called()
    with Session(database) as session:
        saved = session.get(ChatRecord, service.record.id)
        assert saved.finish and not saved.error and saved.sql is None
        assert read_reply(saved.data) == reply
    response = client.get(f"/chat/record/{service.record.id}/data")
    assert response.status_code == 200, response.text
    body = response.json()
    returned = body["data"] if "code" in body else body
    assert returned[REPLY_KEY] == reply
    assert "phone" not in json.dumps(response.json())


@pytest.mark.parametrize("kind", ["answer", "clarify"])
def test_model_reply_never_executes_even_if_payload_contains_sql(
    conversation_environment, kind
):
    database, _client, ds_id = conversation_environment
    service = task(database, ds_id, question="这个表格是什么表？")
    service.execute_sql = Mock(side_effect=AssertionError("Not a query"))
    result = run(
        service,
        {
            "success": True,
            "action": kind,
            "message": "这是销售订单数据，可以统计金额。",
            "sql": "SELECT phone FROM sales_alpha",
        },
    )
    assert result["action"] == kind
    service.execute_sql.assert_not_called()
    with Session(database) as session:
        saved = session.get(ChatRecord, service.record.id)
        assert saved.error is None and saved.finish and saved.sql is None


def test_selected_month_becomes_explicit_followup_and_runs_authorized_query(
    conversation_environment,
):
    database, _client, ds_id = conversation_environment
    first = task(database, ds_id, question="查25号详情")
    clarified = run(first, {})
    second = followup(database, first, clarified["reply"]["options"][5]["question"])
    result = run(
        second,
        {
            "success": True,
            "action": "query",
            "sql": "SELECT id, created_at FROM sales_alpha WHERE created_at = '2026-09-25'",
            "tables": ["sales_alpha"],
        },
    )
    assert result["data"]["data"][0]["id"] == 1
    assert len(result["data"]["data"]) == 1
    assert "2026-09-25" in second.llm.sql_contexts[0]
    assert "phone" not in second.llm.sql_contexts[0]
    third = followup(database, second, "解释刚才的结果")
    run(third, {"action": "answer", "message": "刚才返回了一笔订单。"})
    context = third.llm.sql_contexts[0]
    assert context.index("查25号详情") < context.index("补充条件：查询日期明确为")
    assert context.count("查25号详情") == 3  # Two user turns plus the query summary.
    assert (
        context.count("补充条件：查询日期明确为") == 2
    )  # One question, one result summary.


def test_unknown_model_action_does_not_execute_sql(conversation_environment):
    database, _client, ds_id = conversation_environment
    service = task(database, ds_id, question="查看订单")
    service.llm = Provider(
        {"success": True, "action": "unknown", "sql": "SELECT id FROM sales_alpha"}
    )
    service.execute_sql = Mock(
        side_effect=AssertionError("Not an accepted query action")
    )
    result = list(service.run_task(in_chat=False, stream=False))[-1]
    assert not result["success"]
    service.execute_sql.assert_not_called()
    with Session(database) as session:
        saved = session.get(ChatRecord, service.record.id)
        assert saved.finish and saved.error and saved.sql is None


def test_explicit_previous_month_is_carried_forward_with_result_summary(
    conversation_environment,
):
    database, _client, ds_id = conversation_environment
    first = task(database, ds_id, question="统计2026年9月订单数量")
    run(
        first,
        {
            "success": True,
            "sql": "SELECT COUNT(*) AS order_count FROM sales_alpha WHERE created_at >= '2026-09-01'",
            "tables": ["sales_alpha"],
        },
    )
    second = followup(database, first, "看看25号详情")
    result = run(
        second,
        {
            "success": True,
            "sql": "SELECT id FROM sales_alpha WHERE created_at = '2026-09-25'",
            "tables": ["sales_alpha"],
        },
    )
    assert result.get("action") != "clarify"
    context = second.llm.sql_contexts[0]
    assert "resolved_date_context" in context and "numeric_results" in context
    assert "private-a" not in context and "phone" not in context


def test_zero_rows_are_normal_and_analysis_never_asks_for_upload(
    conversation_environment,
):
    database, _client, ds_id = conversation_environment
    service = task(database, ds_id, question="查询2026年10月25日订单")
    result = run(
        service,
        {
            "success": True,
            "sql": "SELECT id FROM sales_alpha WHERE created_at = '2026-10-25'",
            "tables": ["sales_alpha"],
        },
    )
    assert result["data"]["data"] == []
    assert result["data"][REPLY_KEY]["kind"] == "result"
    assert "0条" in result["data"][REPLY_KEY]["message"]
    service.llm.stream = Mock(
        side_effect=AssertionError("No model analysis for zero rows")
    )
    with Session(database) as session:
        analysis = list(service.generate_analysis(session))
    assert "匹配记录" in analysis[0]["content"] and "CSV" not in analysis[0]["content"]
    service.llm.stream.assert_not_called()


def test_revoked_scope_hides_previous_confirmation_card(conversation_environment):
    database, client, ds_id = conversation_environment
    service = task(database, ds_id, question="查25号订单")
    run(service, {})
    with Session(database) as session:
        field = (
            session.query(CoreField).filter(CoreField.field_name == "created_at").one()
        )
        field.checked = False
        session.add(field)
        session.commit()
    response = client.get(f"/chat/record/{service.record.id}/data")
    assert response.status_code != 200 or response.json().get("code") != 0
    assert "2026年9月25日" not in response.text
