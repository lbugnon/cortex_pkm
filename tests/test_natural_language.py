"""Tests for natural language date and tag parsing."""

import pytest
from datetime import datetime, timedelta
from cor.utils import parse_natural_language_text


class TestParseNaturalLanguageText:
    """Test natural language text parsing for dates and tags."""

    def test_parse_due_date_simple(self):
        """Test parsing 'due tomorrow'."""
        text = "finish the pipeline due tomorrow"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "finish the pipeline"
        assert due_date is not None
        assert tags == []
        # Check that parsed date is roughly tomorrow (within reasonable bounds)
        tomorrow = datetime.now() + timedelta(days=1)
        assert abs((due_date - tomorrow).days) <= 1

    def test_parse_due_date_with_colon(self):
        """Test parsing 'due: <date>'."""
        text = "complete report due: next friday"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "complete report"
        assert due_date is not None
        assert tags == []

    def test_parse_due_date_next_week(self):
        """Test parsing 'due next week'."""
        text = "review code due next week"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        # Note: "next week" may not be parsed by all date parsers
        # If it fails to parse, the text should remain unchanged
        if due_date:
            assert cleaned == "review code"
            # Should be roughly 7 days from now
            next_week = datetime.now() + timedelta(days=7)
            assert abs((due_date - next_week).days) <= 3
        else:
            # If not parsed, text should be unchanged
            assert cleaned == text

    def test_parse_tags_single(self):
        """Test parsing single tag."""
        text = "fix bug tag urgent"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "fix bug"
        assert due_date is None
        assert tags == ["urgent"]

    def test_parse_tags_multiple(self):
        """Test parsing multiple tags."""
        text = "implement feature tag ml nlp research"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "implement feature"
        assert due_date is None
        assert tags == ["ml", "nlp", "research"]

    def test_parse_tags_with_colon(self):
        """Test parsing 'tag: <tags>'."""
        text = "update docs tag: documentation urgent"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "update docs"
        assert due_date is None
        assert tags == ["documentation", "urgent"]

    def test_parse_both_due_and_tags(self):
        """Test parsing both due date and tags."""
        text = "finish project due next friday tag urgent ml"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "finish project"
        assert due_date is not None
        assert tags == ["urgent", "ml"]

    def test_parse_both_reversed_order(self):
        """Test parsing tags before due date."""
        text = "fix issue tag bugfix due tomorrow"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "fix issue"
        assert due_date is not None
        assert tags == ["bugfix"]

    def test_parse_no_keywords(self):
        """Test text without due or tag keywords."""
        text = "just a normal task description"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "just a normal task description"
        assert due_date is None
        assert tags == []

    def test_parse_empty_text(self):
        """Test empty text."""
        cleaned, due_date, tags = parse_natural_language_text("")
        
        assert cleaned == ""
        assert due_date is None
        assert tags == []

    def test_parse_none_text(self):
        """Test None text."""
        cleaned, due_date, tags = parse_natural_language_text(None)
        
        assert cleaned is None
        assert due_date is None
        assert tags == []

    def test_parse_due_date_specific(self):
        """Test parsing specific date formats."""
        text = "meeting notes due 2026-02-15"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "meeting notes"
        assert due_date is not None
        assert due_date.year == 2026
        assert due_date.month == 2
        assert due_date.day == 15

    def test_parse_tags_with_hyphens(self):
        """Test parsing tags with hyphens."""
        text = "new feature tag machine-learning high-priority"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "new feature"
        assert due_date is None
        assert "machine-learning" in tags
        assert "high-priority" in tags

    def test_parse_case_insensitive(self):
        """Test that keywords are case-insensitive."""
        text = "task DUE tomorrow TAG urgent"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "task"
        assert due_date is not None
        assert tags == ["urgent"]


class TestParseNaturalLanguageShortHourFormat:
    """Test short hour format 'in Xh' that search_dates doesn't handle."""

    def test_parse_due_in_5h(self):
        """Test parsing 'due in 5h' (short form)."""
        text = "reminder due in 5h"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "reminder"
        assert due_date is not None
        # Should be approximately 5 hours from now
        expected = datetime.now() + timedelta(hours=5)
        diff = abs((due_date - expected).total_seconds())
        assert diff < 60  # Within 1 minute

    def test_parse_due_in_2h(self):
        """Test parsing 'due in 2h'."""
        text = "quick task due in 2h"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "quick task"
        assert due_date is not None
        expected = datetime.now() + timedelta(hours=2)
        diff = abs((due_date - expected).total_seconds())
        assert diff < 60

    def test_parse_due_in_5h_with_tags(self):
        """Test parsing 'due in 5h' with tags."""
        text = "deploy due in 5h tag urgent"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "deploy"
        assert due_date is not None
        assert "urgent" in tags
        expected = datetime.now() + timedelta(hours=5)
        diff = abs((due_date - expected).total_seconds())
        assert diff < 60


class TestParseNaturalLanguageTimeKeywords:
    """Test time keywords (morning, afternoon, etc.) in natural language date parsing."""

    def test_parse_due_tomorrow_morning(self):
        """Test parsing 'due tomorrow morning'."""
        text = "review code due tomorrow morning"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "review code"
        assert due_date is not None
        assert due_date.hour == 9
        assert due_date.minute == 0
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        assert due_date.date() == tomorrow

    def test_parse_due_tomorrow_afternoon(self):
        """Test parsing 'due tomorrow afternoon'."""
        text = "submit report due tomorrow afternoon"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "submit report"
        assert due_date is not None
        assert due_date.hour == 14
        assert due_date.minute == 0
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        assert due_date.date() == tomorrow

    def test_parse_due_tomorrow_evening(self):
        """Test parsing 'due tomorrow evening'."""
        text = "meeting due tomorrow evening"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "meeting"
        assert due_date is not None
        assert due_date.hour == 18
        assert due_date.minute == 0
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        assert due_date.date() == tomorrow

    def test_parse_due_noon(self):
        """Test parsing 'due tomorrow noon'."""
        text = "lunch meeting due tomorrow noon"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "lunch meeting"
        assert due_date is not None
        assert due_date.hour == 12
        assert due_date.minute == 0
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        assert due_date.date() == tomorrow

    def test_parse_due_night(self):
        """Test parsing 'due tomorrow night'."""
        text = "security check due tomorrow night"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "security check"
        assert due_date is not None
        assert due_date.hour == 21
        assert due_date.minute == 0
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        assert due_date.date() == tomorrow

    def test_parse_due_with_time_and_tags(self):
        """Test parsing due date with morning keyword and tags."""
        text = "deploy app due tomorrow morning tag urgent production"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "deploy app"
        assert due_date is not None
        assert due_date.hour == 9
        assert due_date.minute == 0
        assert "urgent" in tags
        assert "production" in tags

    def test_parse_due_next_friday_morning(self):
        """Test parsing 'due next friday morning'."""
        text = "demo due next friday morning"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "demo"
        assert due_date is not None
        assert due_date.hour == 9
        assert due_date.minute == 0
        # Should be a Friday
        assert due_date.weekday() == 4  # Friday is 4 (Monday=0)

    def test_parse_due_with_explicit_time_overrides_keyword(self):
        """Test that explicit time (8pm) takes precedence over keywords."""
        text = "meeting due tomorrow 8pm"
        cleaned, due_date, tags = parse_natural_language_text(text)
        
        assert cleaned == "meeting"
        assert due_date is not None
        # dateparser handles 8pm correctly
        assert due_date.hour == 20
        assert due_date.minute == 0
