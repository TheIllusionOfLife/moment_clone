import sys
from unittest.mock import MagicMock
import pathlib
import pytest

# Mock google.genai to avoid import errors or API calls during test collection/execution
# We must do this before importing knowledge_base.ingest because it initializes the client at module level
sys.modules["google.genai"] = MagicMock() # type: ignore

from knowledge_base.ingest import _parse_principles # noqa: E402

def test_parse_principles_basic(tmp_path):
    """Test parsing a standard markdown file with headers and lists."""
    md_file = tmp_path / "basic.md"
    md_file.write_text(
        "## Category One\n"
        "- Principle 1\n"
        "* Principle 2\n"
        "\n"
        "## Category Two\n"
        "- Principle 3",
        encoding="utf-8"
    )

    expected = [
        ("Category One", "Principle 1"),
        ("Category One", "Principle 2"),
        ("Category Two", "Principle 3"),
    ]

    assert _parse_principles(md_file) == expected

def test_parse_principles_fallback_category(tmp_path):
    """Test using filename as fallback category when no headers are present."""
    md_file = tmp_path / "fallback.md"
    md_file.write_text(
        "- Principle 1\n"
        "- Principle 2",
        encoding="utf-8"
    )

    expected = [
        ("fallback", "Principle 1"),
        ("fallback", "Principle 2"),
    ]

    assert _parse_principles(md_file) == expected

def test_parse_principles_empty_file(tmp_path):
    """Test parsing an empty file returns empty list."""
    md_file = tmp_path / "empty.md"
    md_file.write_text("", encoding="utf-8")
    assert _parse_principles(md_file) == []

def test_parse_principles_no_list_items(tmp_path):
    """Test file with content but no list items returns empty list."""
    md_file = tmp_path / "text_only.md"
    md_file.write_text(
        "Just some text\n"
        "## Header but no items\n"
        "More text",
        encoding="utf-8"
    )
    assert _parse_principles(md_file) == []

def test_parse_principles_whitespace_handling(tmp_path):
    """Test handling of whitespace around headers and list items."""
    md_file = tmp_path / "whitespace.md"
    md_file.write_text(
        "   ##   Spaced Category   \n"
        "  -   Spaced Principle   \n"
        "\n",
        encoding="utf-8"
    )

    expected = [
        ("Spaced Category", "Spaced Principle"),
    ]

    assert _parse_principles(md_file) == expected

def test_parse_principles_mixed_formatting(tmp_path):
    """Test mixed list markers and empty lines."""
    md_file = tmp_path / "mixed.md"
    md_file.write_text(
        "## Main\n"
        "- Item 1\n"
        "\n"
        "* Item 2\n"
        "  - Item 3 (indented)\n", # Indented items are NOT handled by current logic unless they match startswith("- ")
        encoding="utf-8"
    )

    # Note: Logic is `line.startswith(("- ", "* "))` after `line.strip()`.
    # So "  - Item 3" becomes "- Item 3" after strip, so it SHOULD be caught.

    expected = [
        ("Main", "Item 1"),
        ("Main", "Item 2"),
        ("Main", "Item 3 (indented)"),
    ]

    assert _parse_principles(md_file) == expected
