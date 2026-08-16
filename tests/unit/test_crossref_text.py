"""Crossref text-field decoding (AGE-583).

Regression cover for a defect found by READING live output, not by any assertion: Crossref
returns titles HTML-escaped, and every existing fixture test passed while it was broken
because they only checked that the field was a string.
"""

import pytest

from psychology_mcp.clients.crossref import to_work

pytestmark = pytest.mark.unit


class TestHtmlEntitiesAreDecoded:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("&gt;Finding and Befriending Parts", ">Finding and Befriending Parts"),
            ("Trauma &amp; Recovery", "Trauma & Recovery"),
            ("&lt;i&gt;Emotion&lt;/i&gt; regulation", "<i>Emotion</i> regulation"),
            ("Self&#8208;leadership", "Self\u2010leadership"),  # non-breaking hyphen
        ],
    )
    def test_titles_are_unescaped(self, raw, expected):
        assert to_work({"title": [raw], "type": "book-chapter"}).title == expected

    def test_container_title_is_unescaped(self):
        work = to_work({"title": ["x"], "container-title": ["Journal &amp; Review"]})
        assert work.venue == "Journal & Review"

    def test_publisher_is_unescaped(self):
        work = to_work({"title": ["x"], "publisher": "Taylor &amp; Francis"})
        assert work.publisher == "Taylor & Francis"

    def test_plain_text_is_untouched(self):
        assert (
            to_work({"title": ["Emotions of normal people."]}).title == "Emotions of normal people."
        )

    def test_absent_fields_stay_none(self):
        work = to_work({"type": "book"})
        assert work.title is None and work.venue is None and work.publisher is None
