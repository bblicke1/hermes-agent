"""Durable delivery attribution across crash persistence and transcript readers (#198)."""
from types import SimpleNamespace

import pytest

from agent.background_review import _digest_history, spawn_background_review_thread
from agent.context_compressor import ContextCompressor
from agent.memory_manager import _redact_messages_for_egress
from agent.session_persistence import _db_flush_collect
from agent.turn_context import _stage_turn_user_message, build_api_messages
from hermes_state import SessionDB
from tools.session_search_tool import _read_session
from hermes_cli.web_routers.sessions import _project_for_display
from tui_gateway.server import _history_to_messages

AUTHOR = {"id": "bot:alpha", "name": "Alpha", "is_bot": True}


def test_author_survives_crash_flush_resume_search_memory_and_summary(tmp_path):
    agent = SimpleNamespace(_turn_author=AUTHOR, _last_flushed_db_idx=0, session_id="synthetic")
    message, _ = _stage_turn_user_message(agent, "work order", None, None, None, None, {"source": "fixture"})
    rows, _ = _db_flush_collect(agent, [message], [])
    with SessionDB(tmp_path / "state.db") as db:
        db.create_session("synthetic", source="tui")
        db.append_messages_batch("synthetic", rows)
        restored = db.get_messages_as_conversation("synthetic")
        import json
        searched = json.loads(_read_session(db, "synthetic"))["messages"]
    for row in [restored[0], searched[0], _redact_messages_for_egress(restored)[0]]:
        assert row["display_kind"] == "delivery"
        assert row["display_metadata"] == {"source": "fixture", "author": AUTHOR}
        assert row["role"] == "user"  # Provider role remains independent of transcript author.
    tui_row = _history_to_messages(restored)[0]
    relay_row = _project_for_display(restored)[0]
    for row, content_key in [(tui_row, "text"), (relay_row, "content")]:
        assert row["role"] == "system"
        assert row[content_key] == "Alpha: work order"
        assert row["display_metadata"]["author"] == AUTHOR
    assert restored[0]["role"] == "user" and restored[0]["content"] == "work order"
    compressor = ContextCompressor.__new__(ContextCompressor)
    summary = compressor._serialize_for_summary(restored)
    assert 'BOT {"id":"bot:alpha","name":"Alpha","is_bot":true}' in summary
    assert "[USER]" not in summary
    anchors = compressor._fallback_anchors(restored)
    assert anchors["user_asks"] == []
    assert anchors["last_dropped_turns"][0].startswith("BOT ")


@pytest.mark.parametrize("kind", [None, "hidden", "process_complete"])
def test_transport_author_merges_metadata_without_overwriting_event_type(kind):
    agent = SimpleNamespace(_turn_author=AUTHOR)
    supplied = {"task_count": 1, "author": {"name": "claimed"}}
    message, _ = _stage_turn_user_message(agent, "fixture", None, None, None, kind, supplied)
    assert message["display_kind"] == (kind or "delivery")
    assert message["display_metadata"] == {"task_count": 1, "author": AUTHOR}
    assert supplied["author"] == {"name": "claimed"}


def test_later_human_turn_does_not_inherit_bot_attribution():
    agent = SimpleNamespace(_turn_author=AUTHOR)
    bot, _ = _stage_turn_user_message(agent, "bot", None, None, None, None, None)
    agent._turn_author = None
    human, _ = _stage_turn_user_message(agent, "Brad", None, None, None, None, None)
    assert bot["display_metadata"]["author"] == AUTHOR
    assert "display_kind" not in human and "display_metadata" not in human


def test_memory_skill_review_retains_bot_provenance_without_mutating_cached_history():
    bot = {"role": "user", "content": "bot request", "display_kind": "delivery", "display_metadata": {"author": AUTHOR}}
    history = [bot, {"role": "assistant", "content": "done"}]
    digest = _digest_history(history, tail=1)[0]["content"]
    assert 'BOT {"id":"bot:alpha"' in digest and "USER: bot request" not in digest
    _, prompt = spawn_background_review_thread(SimpleNamespace(), history, review_memory=True, task_cfg={})
    assert 'Transcript row 0: BOT {"id":"bot:alpha"' in prompt
    assert history[0] is bot and bot["content"] == "bot request"


def test_provider_wire_drops_author_metadata_and_preserves_cached_content():
    agent = SimpleNamespace(_current_turn_timestamp=1, ephemeral_system_prompt=None,
                            _copy_reasoning_content_for_api=lambda source, target: None,
                            _should_sanitize_tool_calls=lambda: False)
    history = [{"role": "user", "content": "work order", "display_kind": "delivery",
                "display_metadata": {"author": AUTHOR}}]
    wire, _ = build_api_messages(agent, history, current_turn_user_idx=0, ext_prefetch_cache=None,
                                 plugin_user_context=None, moa_config=None, active_system_prompt="")
    assert wire == [{"role": "user", "content": "work order"}]
    assert history[0]["display_metadata"]["author"] == AUTHOR
