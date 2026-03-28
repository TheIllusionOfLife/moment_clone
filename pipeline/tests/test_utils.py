"""Tests for pipeline/utils.py."""

import pytest

from pipeline.utils import parse_json_response


def test_parse_json_plain():
    raw = '{"key": "value"}'
    assert parse_json_response(raw) == {"key": "value"}


def test_parse_json_with_backtick_fence():
    raw = '```json\n{"key": "value"}\n```'
    assert parse_json_response(raw) == {"key": "value"}


def test_parse_json_with_plain_fence():
    raw = '```\n{"key": "value"}\n```'
    assert parse_json_response(raw) == {"key": "value"}


def test_parse_json_invalid_raises():
    with pytest.raises(ValueError, match="No JSON object found"):
        parse_json_response("not json")
