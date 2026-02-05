"""Tests for slot_analyzer module."""

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
from src.services.slot_analyzer import SlotPatternAnalyzer


class TestSlotPatternAnalyzer:
    """Tests for SlotPatternAnalyzer class."""

    @pytest.fixture
    def temp_data_file(self, tmp_path):
        """Create a temporary data file."""
        return tmp_path / "slot_patterns.json"

    def test_init_creates_directory(self, temp_data_file):
        """Test that initialization creates the data directory."""
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        assert temp_data_file.parent.exists()

    def test_init_loads_existing_data(self, temp_data_file):
        """Test that initialization loads existing data."""
        # Create existing data
        existing_data = {
            "slots": [
                {
                    "country": "nld",
                    "centre": "Amsterdam",
                    "category": "Tourism",
                    "slot_date": "2024-01-15",
                    "slot_time": "10:00",
                    "found_at": "2024-01-10T08:00:00",
                    "found_hour": 8,
                    "found_weekday": "Wednesday",
                    "duration_seconds": None,
                }
            ],
            "stats": {},
        }
        temp_data_file.write_text(json.dumps(existing_data))

        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        assert len(analyzer._patterns["slots"]) == 1
        assert analyzer._patterns["slots"][0]["country"] == "nld"

    def test_init_empty_when_file_not_exists(self, temp_data_file):
        """Test initialization when file doesn't exist."""
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        assert analyzer._patterns == {"slots": [], "stats": {}}

    def test_record_slot_found(self, temp_data_file):
        """Test recording a found slot."""
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        analyzer.record_slot_found(
            country="nld",
            centre="Amsterdam",
            category="Tourism",
            date="2024-01-15",
            time="10:00",
            duration_seconds=120,
        )

        assert len(analyzer._patterns["slots"]) == 1
        slot = analyzer._patterns["slots"][0]
        assert slot["country"] == "nld"
        assert slot["centre"] == "Amsterdam"
        assert slot["category"] == "Tourism"
        assert slot["slot_date"] == "2024-01-15"
        assert slot["slot_time"] == "10:00"
        assert slot["duration_seconds"] == 120
        assert "found_at" in slot
        assert "found_hour" in slot
        assert "found_weekday" in slot

    def test_record_slot_found_saves_to_file(self, temp_data_file):
        """Test that recording a slot saves to file."""
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        analyzer.record_slot_found(
            country="nld", centre="Amsterdam", category="Tourism", date="2024-01-15", time="10:00"
        )

        # Verify file was created and contains data
        assert temp_data_file.exists()
        with open(temp_data_file, "r") as f:
            data = json.load(f)
        assert len(data["slots"]) == 1

    def test_analyze_patterns_no_data(self, temp_data_file):
        """Test analyze_patterns when there's no data."""
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        analysis = analyzer.analyze_patterns(days=30)

        assert "message" in analysis
        assert analysis["message"] == "Yeterli veri yok"

    def test_analyze_patterns_with_data(self, temp_data_file):
        """Test analyze_patterns with sample data."""
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        # Add some sample slots
        now = datetime.now()
        for i in range(10):
            found_at = now - timedelta(days=i)
            analyzer._patterns["slots"].append(
                {
                    "country": "nld",
                    "centre": "Amsterdam",
                    "category": "Tourism",
                    "slot_date": "2024-01-15",
                    "slot_time": "10:00",
                    "found_at": found_at.isoformat(),
                    "found_hour": 9,
                    "found_weekday": "Monday",
                    "duration_seconds": None,
                }
            )

        analysis = analyzer.analyze_patterns(days=30)

        assert analysis["period_days"] == 30
        assert analysis["total_slots_found"] == 10
        assert "best_hours" in analysis
        assert "best_days" in analysis
        assert "best_centres" in analysis
        assert "avg_slots_per_day" in analysis

    def test_analyze_patterns_filters_old_data(self, temp_data_file):
        """Test that analyze_patterns filters out old data."""
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        # Add old slot (40 days ago)
        old_date = datetime.now() - timedelta(days=40)
        analyzer._patterns["slots"].append(
            {
                "country": "nld",
                "centre": "Amsterdam",
                "category": "Tourism",
                "slot_date": "2024-01-15",
                "slot_time": "10:00",
                "found_at": old_date.isoformat(),
                "found_hour": 9,
                "found_weekday": "Monday",
                "duration_seconds": None,
            }
        )

        # Add recent slot
        recent_date = datetime.now() - timedelta(days=1)
        analyzer._patterns["slots"].append(
            {
                "country": "nld",
                "centre": "Amsterdam",
                "category": "Tourism",
                "slot_date": "2024-01-15",
                "slot_time": "10:00",
                "found_at": recent_date.isoformat(),
                "found_hour": 10,
                "found_weekday": "Tuesday",
                "duration_seconds": None,
            }
        )

        analysis = analyzer.analyze_patterns(days=30)

        # Should only include the recent slot
        assert analysis["total_slots_found"] == 1

    def test_generate_weekly_report_no_data(self, temp_data_file):
        """Test generating weekly report with no data."""
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        report = analyzer.generate_weekly_report()

        assert "Henüz yeterli veri toplanmadı" in report

    def test_generate_weekly_report_with_data(self, temp_data_file):
        """Test generating weekly report with data."""
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        # Add sample data
        now = datetime.now()
        for i in range(5):
            found_at = now - timedelta(days=i)
            analyzer._patterns["slots"].append(
                {
                    "country": "nld",
                    "centre": "Amsterdam",
                    "category": "Tourism",
                    "slot_date": "2024-01-15",
                    "slot_time": "10:00",
                    "found_at": found_at.isoformat(),
                    "found_hour": 9,
                    "found_weekday": "Monday",
                    "duration_seconds": None,
                }
            )

        report = analyzer.generate_weekly_report()

        assert "Haftalık Slot Raporu" in report
        assert "Toplam slot bulundu: 5" in report
        assert "En İyi Saatler" in report
        assert "En İyi Günler" in report
        assert "En Aktif Merkezler" in report
