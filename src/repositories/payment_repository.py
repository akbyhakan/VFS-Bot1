"""Payment repository implementation."""

import logging
from typing import Any, Dict, List, Optional

from src.models.database import Database
from src.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class PaymentCard:
    """Payment card entity model."""

    def __init__(
        self,
        id: int,
        card_holder_name: str,
        card_number: Optional[str] = None,
        card_number_masked: Optional[str] = None,
        expiry_month: Optional[str] = None,
        expiry_year: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        """Initialize payment card entity."""
        self.id = id
        self.card_holder_name = card_holder_name
        self.card_number = card_number
        self.card_number_masked = card_number_masked
        self.expiry_month = expiry_month
        self.expiry_year = expiry_year
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert payment card to dictionary."""
        result = {
            "id": self.id,
            "card_holder_name": self.card_holder_name,
            "expiry_month": self.expiry_month,
            "expiry_year": self.expiry_year,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.card_number:
            result["card_number"] = self.card_number
        if self.card_number_masked:
            result["card_number_masked"] = self.card_number_masked
        return result


class PaymentRepository(BaseRepository[PaymentCard]):
    """Repository for payment card CRUD operations."""

    def __init__(self, database: Database):
        """
        Initialize payment repository.

        Args:
            database: Database instance
        """
        super().__init__(database)

    async def get_by_id(self, id: int) -> Optional[PaymentCard]:
        """
        Get payment card by ID with decrypted card number.

        Args:
            id: Card ID

        Returns:
            PaymentCard entity or None if not found
        """
        card_dict = await self.db.get_payment_card()
        if card_dict is None or card_dict.get("id") != id:
            return None

        return PaymentCard(
            id=card_dict["id"],
            card_holder_name=card_dict["card_holder_name"],
            card_number=card_dict.get("card_number"),
            expiry_month=card_dict.get("expiry_month"),
            expiry_year=card_dict.get("expiry_year"),
            created_at=card_dict.get("created_at"),
            updated_at=card_dict.get("updated_at"),
        )

    async def get(self) -> Optional[PaymentCard]:
        """
        Get the saved payment card with decrypted card number.

        Returns:
            PaymentCard entity or None if not found
        """
        card_dict = await self.db.get_payment_card()
        if card_dict is None:
            return None

        return PaymentCard(
            id=card_dict["id"],
            card_holder_name=card_dict["card_holder_name"],
            card_number=card_dict.get("card_number"),
            expiry_month=card_dict.get("expiry_month"),
            expiry_year=card_dict.get("expiry_year"),
            created_at=card_dict.get("created_at"),
            updated_at=card_dict.get("updated_at"),
        )

    async def get_masked(self) -> Optional[PaymentCard]:
        """
        Get the saved payment card with masked card number.

        Returns:
            PaymentCard entity or None if not found
        """
        card_dict = await self.db.get_payment_card_masked()
        if card_dict is None:
            return None

        return PaymentCard(
            id=card_dict["id"],
            card_holder_name=card_dict["card_holder_name"],
            card_number_masked=card_dict.get("card_number_masked"),
            expiry_month=card_dict.get("expiry_month"),
            expiry_year=card_dict.get("expiry_year"),
            created_at=card_dict.get("created_at"),
            updated_at=card_dict.get("updated_at"),
        )

    async def get_all(self, limit: int = 100) -> List[PaymentCard]:
        """
        Get all payment cards.

        Note: In current implementation, only one card is stored at a time.

        Args:
            limit: Maximum number of cards to return

        Returns:
            List of payment card entities
        """
        card = await self.get()
        return [card] if card else []

    async def create(self, data: Dict[str, Any]) -> int:
        """
        Create new payment card (delegates to Database.save_payment_card).

        Args:
            data: Payment card data

        Returns:
            Created card ID
        """
        return await self.db.save_payment_card(card_data=data)

    async def update(self, id: int, data: Dict[str, Any]) -> bool:
        """
        Update payment card (delegates to Database.save_payment_card).

        Note: save_payment_card handles both create and update.

        Args:
            id: Card ID
            data: Update data

        Returns:
            True if updated, False otherwise
        """
        try:
            await self.db.save_payment_card(card_data=data)
            return True
        except Exception as e:
            logger.error(f"Failed to update payment card: {e}")
            return False

    async def delete(self, id: int = 0) -> bool:
        """
        Delete payment card (delegates to Database.delete_payment_card).

        Args:
            id: Card ID (not used as only one card exists)

        Returns:
            True if deleted, False otherwise
        """
        return await self.db.delete_payment_card()
