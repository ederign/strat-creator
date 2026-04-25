import os
import platform
import signal
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from jira_utils import markdown_to_adf, adf_to_markdown, normalize_for_compare, strip_metadata


if platform.system() != "Windows":
    @pytest.fixture(autouse=True)
    def timeout_guard():
        """Kill the test after 5 seconds to catch infinite loops."""
        def handler(signum, frame):
            raise TimeoutError("Test exceeded 5-second timeout — possible infinite loop")
        old = signal.signal(signal.SIGALRM, handler)
        signal.alarm(5)
        yield
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


# ─── markdown_to_adf ────────────────────────────────────────────────────────


class TestMarkdownToAdf:

    def test_paragraph(self):
        adf = markdown_to_adf("Hello world")
        assert adf["type"] == "doc"
        assert adf["content"][0]["type"] == "paragraph"
        assert adf["content"][0]["content"][0]["text"] == "Hello world"

    def test_headings_h1_to_h6(self):
        for level in range(1, 7):
            prefix = "#" * level
            adf = markdown_to_adf(f"{prefix} Heading {level}")
            heading = adf["content"][0]
            assert heading["type"] == "heading"
            assert heading["attrs"]["level"] == level
            assert heading["content"][0]["text"] == f"Heading {level}"

    def test_bullet_list(self):
        md = "- Item one\n- Item two\n- Item three"
        adf = markdown_to_adf(md)
        bl = adf["content"][0]
        assert bl["type"] == "bulletList"
        assert len(bl["content"]) == 3
        assert bl["content"][0]["type"] == "listItem"

    def test_ordered_list(self):
        md = "1. First\n2. Second\n3. Third"
        adf = markdown_to_adf(md)
        ol = adf["content"][0]
        assert ol["type"] == "orderedList"
        assert len(ol["content"]) == 3

    def test_code_block_with_language(self):
        md = "```python\nprint('hello')\n```"
        adf = markdown_to_adf(md)
        cb = adf["content"][0]
        assert cb["type"] == "codeBlock"
        assert cb["attrs"]["language"] == "python"
        assert cb["content"][0]["text"] == "print('hello')"

    def test_code_block_no_language(self):
        md = "```\nsome code\n```"
        adf = markdown_to_adf(md)
        cb = adf["content"][0]
        assert cb["type"] == "codeBlock"
        assert cb["content"][0]["text"] == "some code"

    def test_table(self):
        md = (
            "| Name | Value |\n"
            "|------|-------|\n"
            "| foo  | bar   |\n"
            "| baz  | qux   |\n"
        )
        adf = markdown_to_adf(md)
        table = adf["content"][0]
        assert table["type"] == "table"
        assert len(table["content"]) == 3  # header + 2 data rows
        header_row = table["content"][0]
        assert header_row["content"][0]["type"] == "tableHeader"
        data_row = table["content"][1]
        assert data_row["content"][0]["type"] == "tableCell"

    def test_blockquote(self):
        md = "> Quoted text\n> More quoted"
        adf = markdown_to_adf(md)
        bq = adf["content"][0]
        assert bq["type"] == "blockquote"

    def test_link(self):
        md = "Check [this link](https://example.com) out"
        adf = markdown_to_adf(md)
        nodes = adf["content"][0]["content"]
        link_node = [n for n in nodes if n.get("marks") and
                     any(m["type"] == "link" for m in n["marks"])]
        assert len(link_node) == 1
        mark = link_node[0]["marks"][0]
        assert mark["attrs"]["href"] == "https://example.com"
        assert link_node[0]["text"] == "this link"

    def test_bold(self):
        adf = markdown_to_adf("**bold text**")
        node = adf["content"][0]["content"][0]
        assert node["text"] == "bold text"
        assert any(m["type"] == "strong" for m in node["marks"])

    def test_italic(self):
        adf = markdown_to_adf("*italic text*")
        node = adf["content"][0]["content"][0]
        assert node["text"] == "italic text"
        assert any(m["type"] == "em" for m in node["marks"])

    def test_strikethrough(self):
        adf = markdown_to_adf("~~struck~~")
        node = adf["content"][0]["content"][0]
        assert node["text"] == "struck"
        assert any(m["type"] == "strike" for m in node["marks"])

    def test_inline_code(self):
        adf = markdown_to_adf("`code span`")
        node = adf["content"][0]["content"][0]
        assert node["text"] == "code span"
        assert any(m["type"] == "code" for m in node["marks"])

    def test_horizontal_rule(self):
        adf = markdown_to_adf("---")
        assert adf["content"][0]["type"] == "rule"

    def test_empty_input_returns_valid_doc(self):
        adf = markdown_to_adf("")
        assert adf["type"] == "doc"
        assert adf["version"] == 1
        assert len(adf["content"]) >= 1

    def test_malformed_heading_no_text(self):
        """Regression: '### ' with no text should not infinite loop."""
        adf = markdown_to_adf("### ")
        heading = adf["content"][0]
        assert heading["type"] == "heading"
        assert heading["attrs"]["level"] == 3

    def test_malformed_heading_only_hashes(self):
        adf = markdown_to_adf("## ")
        heading = adf["content"][0]
        assert heading["type"] == "heading"
        assert heading["attrs"]["level"] == 2


# ─── adf_to_markdown ────────────────────────────────────────────────────────


class TestAdfToMarkdown:

    def test_paragraph(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "Hello"}
                ]}
            ]
        }
        md = adf_to_markdown(adf)
        assert "Hello" in md

    def test_heading(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [
                {"type": "heading", "attrs": {"level": 2}, "content": [
                    {"type": "text", "text": "Title"}
                ]}
            ]
        }
        md = adf_to_markdown(adf)
        assert md.strip() == "## Title"

    def test_bullet_list(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [{
                "type": "bulletList",
                "content": [
                    {"type": "listItem", "content": [
                        {"type": "paragraph", "content": [
                            {"type": "text", "text": "Item A"}
                        ]}
                    ]},
                    {"type": "listItem", "content": [
                        {"type": "paragraph", "content": [
                            {"type": "text", "text": "Item B"}
                        ]}
                    ]},
                ]
            }]
        }
        md = adf_to_markdown(adf)
        assert "- Item A" in md
        assert "- Item B" in md

    def test_ordered_list(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [{
                "type": "orderedList",
                "content": [
                    {"type": "listItem", "content": [
                        {"type": "paragraph", "content": [
                            {"type": "text", "text": "First"}
                        ]}
                    ]},
                    {"type": "listItem", "content": [
                        {"type": "paragraph", "content": [
                            {"type": "text", "text": "Second"}
                        ]}
                    ]},
                ]
            }]
        }
        md = adf_to_markdown(adf)
        assert "1. First" in md
        assert "2. Second" in md

    def test_code_block_with_language(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [{
                "type": "codeBlock",
                "attrs": {"language": "bash"},
                "content": [{"type": "text", "text": "echo hi"}]
            }]
        }
        md = adf_to_markdown(adf)
        assert "```bash" in md
        assert "echo hi" in md
        assert md.strip().endswith("```")

    def test_blockquote(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [{
                "type": "blockquote",
                "content": [
                    {"type": "paragraph", "content": [
                        {"type": "text", "text": "Quoted"}
                    ]}
                ]
            }]
        }
        md = adf_to_markdown(adf)
        assert "> Quoted" in md

    def test_table(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [{
                "type": "table",
                "content": [
                    {"type": "tableRow", "content": [
                        {"type": "tableHeader", "content": [
                            {"type": "paragraph", "content": [
                                {"type": "text", "text": "Col1"}
                            ]}
                        ]},
                        {"type": "tableHeader", "content": [
                            {"type": "paragraph", "content": [
                                {"type": "text", "text": "Col2"}
                            ]}
                        ]},
                    ]},
                    {"type": "tableRow", "content": [
                        {"type": "tableCell", "content": [
                            {"type": "paragraph", "content": [
                                {"type": "text", "text": "A"}
                            ]}
                        ]},
                        {"type": "tableCell", "content": [
                            {"type": "paragraph", "content": [
                                {"type": "text", "text": "B"}
                            ]}
                        ]},
                    ]},
                ]
            }]
        }
        md = adf_to_markdown(adf)
        assert "Col1" in md
        assert "Col2" in md
        assert "| A |" in md or "A" in md
        assert "---" in md

    def test_bold_mark(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "strong",
                     "marks": [{"type": "strong"}]}
                ]}
            ]
        }
        md = adf_to_markdown(adf)
        assert "**strong**" in md

    def test_italic_mark(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "emphasis",
                     "marks": [{"type": "em"}]}
                ]}
            ]
        }
        md = adf_to_markdown(adf)
        assert "*emphasis*" in md

    def test_strike_mark(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "removed",
                     "marks": [{"type": "strike"}]}
                ]}
            ]
        }
        md = adf_to_markdown(adf)
        assert "~~removed~~" in md

    def test_code_mark(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "fn()",
                     "marks": [{"type": "code"}]}
                ]}
            ]
        }
        md = adf_to_markdown(adf)
        assert "`fn()`" in md

    def test_link_mark(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "click here",
                     "marks": [{"type": "link",
                                "attrs": {"href": "https://example.com"}}]}
                ]}
            ]
        }
        md = adf_to_markdown(adf)
        assert "[click here](https://example.com)" in md

    def test_rule(self):
        adf = {
            "type": "doc", "version": 1,
            "content": [{"type": "rule"}]
        }
        md = adf_to_markdown(adf)
        assert "---" in md

    def test_none_returns_empty(self):
        assert adf_to_markdown(None) == ""

    def test_string_passthrough(self):
        assert adf_to_markdown("raw text") == "raw text"


# ─── Round-trip ──────────────────────────────────────────────────────────────


class TestRoundTrip:

    def test_complete_document_round_trip(self):
        md = (
            "# Main Title\n"
            "\n"
            "A paragraph with **bold** and *italic* text.\n"
            "\n"
            "## Section\n"
            "\n"
            "- Bullet one\n"
            "- Bullet two\n"
            "\n"
            "1. Numbered one\n"
            "2. Numbered two\n"
            "\n"
            "```python\ndef hello():\n    pass\n```\n"
            "\n"
            "> A blockquote\n"
            "\n"
            "---\n"
            "\n"
            "Final paragraph.\n"
        )
        adf = markdown_to_adf(md)
        back = adf_to_markdown(adf)
        normalized_orig = normalize_for_compare(md)
        normalized_back = normalize_for_compare(back)
        assert "Main Title" in normalized_back
        assert "bold" in normalized_back
        assert "italic" in normalized_back
        assert "Bullet one" in normalized_back
        assert "Numbered one" in normalized_back
        assert "def hello():" in normalized_back
        assert "A blockquote" in normalized_back
        assert "Final paragraph." in normalized_back

    def test_table_round_trip(self):
        md = (
            "| Header1 | Header2 |\n"
            "|---------|--------|\n"
            "| Cell1   | Cell2  |\n"
        )
        adf = markdown_to_adf(md)
        back = adf_to_markdown(adf)
        assert "Header1" in back
        assert "Header2" in back
        assert "Cell1" in back
        assert "Cell2" in back

    def test_inline_formatting_round_trip(self):
        md = "Text with **bold**, *italic*, ~~strike~~, and `code`."
        adf = markdown_to_adf(md)
        back = adf_to_markdown(adf)
        assert "**bold**" in back
        assert "*italic*" in back
        assert "~~strike~~" in back
        assert "`code`" in back

    def test_link_round_trip(self):
        md = "Visit [example](https://example.com) for info."
        adf = markdown_to_adf(md)
        back = adf_to_markdown(adf)
        assert "[example](https://example.com)" in back


# ─── normalize_for_compare ───────────────────────────────────────────────────


class TestNormalizeForCompare:

    def test_curly_quotes_to_straight(self):
        text = "“Hello” and ‘world’"
        result = normalize_for_compare(text)
        assert '"Hello"' in result
        assert "'world'" in result

    def test_em_dash_normalized(self):
        result = normalize_for_compare("value—result")
        assert "value--result" in result

    def test_en_dash_to_double_dash(self):
        result = normalize_for_compare("pages 1–5")
        assert "pages 1--5" in result

    def test_non_breaking_space_to_regular(self):
        result = normalize_for_compare("hello\xa0world")
        assert "hello world" in result

    def test_zero_width_chars_stripped(self):
        result = normalize_for_compare("hel​lo‌wo‍rld")
        assert result == "helloworld"

    def test_collapses_multiple_blank_lines(self):
        result = normalize_for_compare("a\n\n\n\nb")
        assert result == "a\n\nb"

    def test_strips_trailing_whitespace(self):
        result = normalize_for_compare("hello   \nworld  ")
        assert "hello\nworld" == result

    def test_arrow_normalization(self):
        result = normalize_for_compare("A → B")
        assert "A -> B" in result


# ─── strip_metadata ─────────────────────────────────────────────────────────


class TestStripMetadata:

    def test_strips_strat_title_heading(self):
        md = "# STRAT-001: My Strategy\n\nBody text."
        result = strip_metadata(md)
        assert "STRAT-001" not in result
        assert "Body text." in result

    def test_strips_rhaistrat_title_heading(self):
        md = "# RHAISTRAT-400: Some Title\n\nContent."
        result = strip_metadata(md)
        assert "RHAISTRAT-400" not in result
        assert "Content." in result

    def test_strips_rfe_title_heading(self):
        md = "# RHAIRFE-1500: Feature Request\n\nDetails."
        result = strip_metadata(md)
        assert "RHAIRFE-1500" not in result
        assert "Details." in result

    def test_strips_html_comments(self):
        md = "Before <!-- hidden --> after"
        result = strip_metadata(md)
        assert "hidden" not in result
        assert "Before" in result
        assert "after" in result

    def test_strips_multiline_html_comments(self):
        md = "Start\n<!-- multi\nline\ncomment -->\nEnd"
        result = strip_metadata(md)
        assert "multi" not in result
        assert "Start" in result
        assert "End" in result

    def test_strips_yaml_frontmatter(self):
        md = "---\nstrat_id: STRAT-001\ntitle: Test\n---\nBody here."
        result = strip_metadata(md)
        assert "strat_id" not in result
        assert "Body here." in result

    def test_strips_legacy_metadata_lines(self):
        md = (
            "**Jira Key**: RHAIRFE-100\n"
            "**Size**: M\n"
            "**Priority**: Major\n"
            "**Source RFE**: RHAIRFE-100\n"
            "\nReal content.\n"
        )
        result = strip_metadata(md)
        assert "**Jira Key**" not in result
        assert "**Size**" not in result
        assert "Real content." in result

    def test_strips_revision_notes_section(self):
        md = (
            "## Description\n"
            "Content.\n"
            "### Revision Notes\n"
            "Note 1.\n"
            "Note 2.\n"
            "## Next Section\n"
            "More content.\n"
        )
        result = strip_metadata(md)
        assert "Note 1." not in result
        assert "Note 2." not in result
        assert "Content." in result
        assert "More content." in result

    def test_strips_review_note_blockquotes(self):
        md = "> *Review note: This was changed.*\n\nParagraph."
        result = strip_metadata(md)
        assert "Review note" not in result
        assert "Paragraph." in result

    def test_preserves_normal_content(self):
        md = (
            "## Overview\n"
            "This is a strategy for improving performance.\n"
            "\n"
            "## Details\n"
            "Technical details here.\n"
        )
        result = strip_metadata(md)
        assert "Overview" in result
        assert "improving performance" in result
        assert "Technical details here." in result

    def test_collapses_excess_blank_lines(self):
        md = "Line 1.\n\n\n\n\nLine 2."
        result = strip_metadata(md)
        assert "\n\n\n" not in result
        assert "Line 1." in result
        assert "Line 2." in result
