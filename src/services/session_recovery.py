"""Gelişmiş session recovery sistemi."""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class SessionRecovery:
    """Bot çökerse kaldığı yerden devam etmesini sağla."""

    CHECKPOINT_STEPS = [
        "initialized",
        "logged_in",
        "centre_selected",
        "category_selected",
        "date_selected",
        "waitlist_detected",
        "waitlist_joined",
        "personal_info_filled",
        "review_page",
        "checkboxes_accepted",
        "payment_started",
        "payment_completed",
        "completed",
    ]

    def __init__(self, checkpoint_file: str = "data/session_checkpoint.json"):
        self.checkpoint_file = Path(checkpoint_file)
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        self._current_checkpoint: Optional[Dict[str, Any]] = None
        self._fernet = self._init_fernet()

    def _init_fernet(self) -> Optional[Fernet]:
        """Initialize Fernet encryption using ENCRYPTION_KEY from environment."""
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            logger.warning(
                "ENCRYPTION_KEY not set - checkpoint data will NOT be encrypted. "
                "Set ENCRYPTION_KEY for secure checkpoint storage."
            )
            return None
        try:
            return Fernet(encryption_key.encode())
        except Exception as e:
            logger.error(f"Failed to initialize Fernet encryption: {e}")
            return None

    def save_checkpoint(self, step: str, user_id: int, context: Dict[str, Any]) -> None:
        """Checkpoint kaydet."""
        if step not in self.CHECKPOINT_STEPS:
            logger.warning(f"Bilinmeyen checkpoint step: {step}")

        checkpoint = {
            "step": step,
            "step_index": self.CHECKPOINT_STEPS.index(step)
            if step in self.CHECKPOINT_STEPS
            else -1,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context,
        }

        self._current_checkpoint = checkpoint

        try:
            json_data = json.dumps(checkpoint, ensure_ascii=False)
            if self._fernet:
                # Encrypt the data before writing
                encrypted_data = self._fernet.encrypt(json_data.encode("utf-8"))
                with open(self.checkpoint_file, "wb") as f:
                    f.write(encrypted_data)
                logger.debug(f"Checkpoint kaydedildi (encrypted): {step}")
            else:
                # Fallback to unencrypted if no encryption key
                with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                    f.write(json_data)
                logger.debug(f"Checkpoint kaydedildi (unencrypted): {step}")
        except Exception as e:
            logger.error(f"Checkpoint kaydetme hatası: {e}")

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Son checkpoint'i yükle."""
        try:
            if not self.checkpoint_file.exists():
                return None

            raw_data = self.checkpoint_file.read_bytes()

            # Try decryption first if encryption is available
            if self._fernet:
                try:
                    decrypted = self._fernet.decrypt(raw_data)
                    checkpoint = json.loads(decrypted.decode("utf-8"))
                    logger.debug("Checkpoint loaded (encrypted)")
                except InvalidToken:
                    # Backward compatibility: try reading as plain JSON
                    logger.warning("Checkpoint file is not encrypted, reading as plaintext (legacy)")
                    checkpoint = json.loads(raw_data.decode("utf-8"))
            else:
                # No encryption available, read as plaintext
                checkpoint = json.loads(raw_data.decode("utf-8"))
                logger.debug("Checkpoint loaded (unencrypted)")

            # 1 saatten eski checkpoint'leri ignore et
            # Support both timezone-aware and naive datetime strings for backward compatibility
            checkpoint_time = datetime.fromisoformat(checkpoint["timestamp"])
            # Make timezone-naive datetimes UTC-aware for comparison
            if checkpoint_time.tzinfo is None:
                checkpoint_time = checkpoint_time.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - checkpoint_time).total_seconds() / 3600

            if age_hours > 1:
                logger.info("Checkpoint 1 saatten eski, ignore ediliyor")
                self.clear_checkpoint()
                return None

            logger.info(
                f"Checkpoint yüklendi: {checkpoint['step']} (user_id: {checkpoint['user_id']})"
            )
            return checkpoint

        except Exception as e:
            logger.error(f"Checkpoint yükleme hatası: {e}")
            return None

    def clear_checkpoint(self) -> None:
        """Checkpoint'i temizle (başarılı tamamlama sonrası)."""
        try:
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
            self._current_checkpoint = None
            logger.debug("Checkpoint temizlendi")
        except Exception as e:
            logger.error(f"Checkpoint temizleme hatası: {e}")

    def can_resume_from(self, step: str) -> bool:
        """Bu step'ten devam edilebilir mi?"""
        checkpoint = self.load_checkpoint()
        if not checkpoint:
            return False

        checkpoint_index: int = checkpoint.get("step_index", -1)
        step_index = self.CHECKPOINT_STEPS.index(step) if step in self.CHECKPOINT_STEPS else -1

        # Checkpoint, istenen step'ten sonra olmalı
        return checkpoint_index >= step_index

    def get_resume_step(self) -> Optional[str]:
        """Devam edilecek step'i getir."""
        checkpoint = self.load_checkpoint()
        if checkpoint:
            step: Optional[str] = checkpoint.get("step")
            return step
        return None

    def get_resume_context(self) -> Dict[str, Any]:
        """Devam edilecek context'i getir."""
        checkpoint = self.load_checkpoint()
        if checkpoint:
            context: Dict[str, Any] = checkpoint.get("context", {})
            return context
        return {}
