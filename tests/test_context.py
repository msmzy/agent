"""Tests for context management and compression."""

import pytest

from repopilot.context.token_counter import TokenCounter
from repopilot.context.cache import CacheManager, CacheStats
from repopilot.context.compressor import ContextCompressor


class TestTokenCounter:
    def test_count_text(self):
        counter = TokenCounter()
        count = counter.count_text("Hello world, this is a test.")
        assert count > 0

    def test_empty_text(self):
        counter = TokenCounter()
        assert counter.count_text("") == 0

    def test_count_messages(self):
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        count = counter.count_messages(messages)
        assert count > 0

    def test_count_tool_message(self):
        counter = TokenCounter()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "1", "content": "file contents here"}
                ],
            }
        ]
        count = counter.count_messages(messages)
        assert count > 0


class TestCacheStats:
    def test_hit_rate(self):
        stats = CacheStats(total_requests=10, cache_hits=7)
        assert stats.hit_rate == 0.7

    def test_zero_requests(self):
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_summary(self):
        stats = CacheStats(total_requests=5, cache_hits=3, cache_read_tokens=1000)
        s = stats.summary()
        assert "5 requests" in s
        assert "60.0%" in s


class TestCacheManager:
    def test_prepare_system_blocks(self):
        cm = CacheManager()
        blocks = cm.prepare_system_blocks("You are a helpful assistant.")
        assert len(blocks) == 1
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}

    def test_prepare_tools(self):
        cm = CacheManager()
        tools = [{"name": "a"}, {"name": "b"}]
        prepared = cm.prepare_tools(tools)
        assert "cache_control" not in prepared[0]
        assert prepared[-1]["cache_control"] == {"type": "ephemeral"}

    def test_prepare_empty_tools(self):
        cm = CacheManager()
        assert cm.prepare_tools([]) == []


class TestContextCompressor:
    def setup_method(self):
        self.counter = TokenCounter()
        self.compressor = ContextCompressor(
            token_counter=self.counter,
            context_window=1000,
            warning_threshold=0.70,
            critical_threshold=0.85,
            max_recent_results=2,
        )

    def test_microcompact_keeps_recent(self):
        messages = []
        for i in range(5):
            messages.append({"role": "assistant", "content": [{"type": "tool_use", "id": f"t{i}", "name": "read", "input": {}}]})
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": f"result {i} " * 100}]})

        result = self.compressor._layer1_microcompact(messages)
        assert len(result) == len(messages)

    def test_context_collapse_folds_old(self):
        messages = []
        for i in range(10):
            messages.append({"role": "user", "content": f"Question {i}"})
            messages.append({"role": "assistant", "content": [{"type": "text", "text": f"Answer {i}"}]})

        result = self.compressor._layer2_context_collapse(messages)
        assert len(result) <= len(messages)

    def test_no_compression_when_small(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": [{"type": "text", "text": "hello"}]},
        ]
        result, compressed = self.compressor.compress_if_needed(messages, 10, 10)
        assert not compressed
