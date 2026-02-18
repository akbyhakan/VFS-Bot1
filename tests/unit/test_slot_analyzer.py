"""Tests for slot_analyzer module."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

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

        assert analyzer is not None
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

    @pytest.mark.asyncio
    async def test_record_slot_found(self, temp_data_file):
        """Test recording a found slot."""
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        await analyzer.record_slot_found_async(
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

    @pytest.mark.asyncio
    async def test_record_slot_found_saves_to_file(self, temp_data_file):
        """Test that recording a slot saves to file."""
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        await analyzer.record_slot_found_async(
            country="nld", centre="Amsterdam", category="Tourism", date="2024-01-15", time="10:00"
        )

        # Flush to ensure data is written to file
        await analyzer.flush()

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
        assert analysis["message"] == "Insufficient data"

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


class TestSlotRetention:
    """Tests for slot pattern retention enforcement."""

    @pytest.fixture
    def temp_data_file(self, tmp_path):
        """Create a temporary data file."""
        return tmp_path / "slot_patterns.json"

    def test_enforce_retention_trims_excess_slots(self, temp_data_file):
        """Test that retention enforcement trims excess slots."""
        from src.services.slot_analyzer import _MAX_SLOT_RECORDS

        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        # Add more than max records
        now = datetime.now()
        for i in range(_MAX_SLOT_RECORDS + 100):
            analyzer._patterns["slots"].append(
                {
                    "country": "nld",
                    "centre": "Amsterdam",
                    "category": "Tourism",
                    "slot_date": "2024-01-15",
                    "slot_time": "10:00",
                    "found_at": (now - timedelta(days=i)).isoformat(),
                    "found_hour": 9,
                    "found_weekday": "Monday",
                }
            )

        # Save data - should trigger retention
        analyzer._save_data_sync()

        # Verify retention was enforced
        assert len(analyzer._patterns["slots"]) == _MAX_SLOT_RECORDS

    def test_retention_keeps_most_recent(self, temp_data_file):
        """Test that retention keeps the most recent records."""
        from src.services.slot_analyzer import _MAX_SLOT_RECORDS

        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        # Add records with identifiable timestamps
        now = datetime.now()
        for i in range(_MAX_SLOT_RECORDS + 10):
            analyzer._patterns["slots"].append(
                {
                    "country": "nld",
                    "centre": f"Centre_{i}",  # Unique identifier
                    "category": "Tourism",
                    "slot_date": "2024-01-15",
                    "slot_time": "10:00",
                    "found_at": (now - timedelta(days=_MAX_SLOT_RECORDS + 10 - i)).isoformat(),
                    "found_hour": 9,
                    "found_weekday": "Monday",
                }
            )

        # Save and enforce retention
        analyzer._save_data_sync()

        # First 10 oldest should be removed
        remaining_centres = [slot["centre"] for slot in analyzer._patterns["slots"]]
        assert "Centre_0" not in remaining_centres
        assert "Centre_9" not in remaining_centres
        assert "Centre_10" in remaining_centres
        assert f"Centre_{_MAX_SLOT_RECORDS + 9}" in remaining_centres

    def test_retention_on_load(self, temp_data_file):
        """Test that retention is enforced when loading data."""
        from src.services.slot_analyzer import _MAX_SLOT_RECORDS

        # Create file with excess records
        now = datetime.now()
        data = {
            "slots": [
                {
                    "country": "nld",
                    "centre": "Amsterdam",
                    "category": "Tourism",
                    "slot_date": "2024-01-15",
                    "slot_time": "10:00",
                    "found_at": (now - timedelta(days=i)).isoformat(),
                    "found_hour": 9,
                    "found_weekday": "Monday",
                }
                for i in range(_MAX_SLOT_RECORDS + 50)
            ],
            "stats": {},
        }
        temp_data_file.write_text(json.dumps(data))

        # Load data - should trigger retention
        analyzer = SlotPatternAnalyzer(str(temp_data_file))

        # Verify retention was enforced
        assert len(analyzer._patterns["slots"]) == _MAX_SLOT_RECORDS
