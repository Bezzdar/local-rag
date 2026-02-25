"""Тесты текстов для Agent-режима."""

from apps.api.services.chat_modes import build_answer


def test_build_answer_agent_includes_name_and_tools():
    text = build_answer(
        mode="agent",
        message="покажи продажи",
        citations=[],
        agent_id="agent_001",
        agent_name="Dash",
        tools=["text-to-sql", "learning-loop"],
    )

    assert "Dash [agent_001]" in text
    assert "text-to-sql, learning-loop" in text
    assert "Запрос принят: покажи продажи" in text
