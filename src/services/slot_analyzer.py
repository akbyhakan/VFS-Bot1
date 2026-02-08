"""Slot pattern analizi ve raporlama."""
import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Batch write constants
_BATCH_SIZE = 10         # Write to disk every N records
_BATCH_INTERVAL = 60.0   # Or every 60 seconds (whichever comes first)


class SlotPatternAnalyzer:
    """Slot açılma pattern'lerini analiz et ve raporla."""

    def __init__(self, data_file: str = "data/slot_patterns.json"):
        self.data_file = Path(data_file)
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self._patterns: Dict[str, Any] = self._load_data()
        self._pending_writes = 0
        self._last_save_time = datetime.now(timezone.utc)

    def _load_data(self) -> Dict[str, Any]:
        """Mevcut pattern verilerini yükle."""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                    return data
            except Exception as e:
                logger.error(f"Pattern data yüklenemedi: {e}")
        return {"slots": [], "stats": {}}

    def _save_data_sync(self) -> None:
        """Pattern verilerini kaydet."""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self._patterns, f, indent=2, ensure_ascii=False)
            self._pending_writes = 0
            self._last_save_time = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"Pattern data kaydedilemedi: {e}")

    def record_slot_found(
        self,
        country: str,
        centre: str,
        category: str,
        date: str,
        time: str,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """Bulunan slot'u kaydet."""
        now = datetime.now(timezone.utc)
        record = {
            "country": country,
            "centre": centre,
            "category": category,
            "slot_date": date,
            "slot_time": time,
            "found_at": now.isoformat(),
            "found_hour": now.hour,
            "found_weekday": now.strftime("%A"),
            "duration_seconds": duration_seconds,
        }
        self._patterns["slots"].append(record)
        self._pending_writes += 1
        self._save_data_sync()
        logger.info(f"Slot pattern kaydedildi: {country}/{centre}")

    async def record_slot_found_async(
        self,
        country: str,
        centre: str,
        category: str,
        date: str,
        time: str,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """Bulunan slot'u kaydet (async version with batching)."""
        now = datetime.now(timezone.utc)
        record = {
            "country": country,
            "centre": centre,
            "category": category,
            "slot_date": date,
            "slot_time": time,
            "found_at": now.isoformat(),
            "found_hour": now.hour,
            "found_weekday": now.strftime("%A"),
            "duration_seconds": duration_seconds,
        }
        self._patterns["slots"].append(record)
        self._pending_writes += 1
        logger.info(f"Slot pattern kaydedildi: {country}/{centre}")
        
        # Check if we should save (batch logic)
        await self._maybe_save()

    async def _maybe_save(self) -> None:
        """Save data if batch size or time interval reached."""
        should_save = False
        
        if self._pending_writes >= _BATCH_SIZE:
            should_save = True
        else:
            elapsed = (datetime.now(timezone.utc) - self._last_save_time).total_seconds()
            if elapsed >= _BATCH_INTERVAL and self._pending_writes > 0:
                should_save = True
        
        if should_save:
            await asyncio.to_thread(self._save_data_sync)

    async def flush(self) -> None:
        """Force write any pending data to disk."""
        if self._pending_writes > 0:
            await asyncio.to_thread(self._save_data_sync)
            logger.info(f"Flushed {self._pending_writes} pending slot records to disk")

    def analyze_patterns(self, days: int = 30) -> Dict[str, Any]:
        """Son N gündeki pattern'leri analiz et."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent_slots = []
        for s in self._patterns.get("slots", []):
            try:
                # Support both timezone-aware and naive datetime strings for backward compatibility
                found_at = datetime.fromisoformat(s["found_at"])
                # Make timezone-naive datetimes UTC-aware for comparison
                if found_at.tzinfo is None:
                    found_at = found_at.replace(tzinfo=timezone.utc)
                if found_at > cutoff:
                    recent_slots.append(s)
            except (ValueError, KeyError):
                continue

        if not recent_slots:
            return {"message": "Yeterli veri yok"}

        # Saat bazlı analiz
        hour_counts: Dict[int, int] = defaultdict(int)
        for slot in recent_slots:
            hour_counts[slot["found_hour"]] += 1

        # Gün bazlı analiz
        day_counts: Dict[str, int] = defaultdict(int)
        for slot in recent_slots:
            day_counts[slot["found_weekday"]] += 1

        # Merkez bazlı analiz
        centre_counts: Dict[str, int] = defaultdict(int)
        for slot in recent_slots:
            centre_counts[slot["centre"]] += 1

        # En iyi saatler (top 3)
        best_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]

        # En iyi günler (top 3)
        best_days = sorted(day_counts.items(), key=lambda x: x[1], reverse=True)[:3]

        # En aktif merkezler
        best_centres = sorted(centre_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "period_days": days,
            "total_slots_found": len(recent_slots),
            "best_hours": [{"hour": f"{h}:00", "count": c} for h, c in best_hours],
            "best_days": [{"day": d, "count": c} for d, c in best_days],
            "best_centres": [{"centre": c, "count": cnt} for c, cnt in best_centres],
            "avg_slots_per_day": round(len(recent_slots) / days, 2),
        }

    def generate_weekly_report(self) -> str:
        """Haftalık Telegram raporu oluştur."""
        analysis = self.analyze_patterns(days=7)

        if "message" in analysis:
            return "📊 Haftalık Rapor: Henüz yeterli veri toplanmadı."

        report = f"""📊 **VFS-Bot Haftalık Slot Raporu**

📈 **Son 7 Günde:**
• Toplam slot bulundu: {analysis['total_slots_found']}
• Günlük ortalama: {analysis['avg_slots_per_day']}

⏰ **En İyi Saatler:**
"""
        for h in analysis["best_hours"]:
            report += f"  • {h['hour']} - {h['count']} slot\n"

        report += "\n📅 **En İyi Günler:**\n"
        for d in analysis["best_days"]:
            report += f"  • {d['day']} - {d['count']} slot\n"

        report += "\n🏢 **En Aktif Merkezler:**\n"
        for c in analysis["best_centres"]:
            report += f"  • {c['centre']} - {c['count']} slot\n"

        return report
