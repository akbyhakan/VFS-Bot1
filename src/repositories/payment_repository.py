"""Payment repository implementation."""

from typing import Any, Dict, List, Optional

from loguru import logger

from src.models.database import Database
from src.repositories.base import BaseRepository
from src.utils.encryption import decrypt_password, encrypt_password


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
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM payment_card LIMIT 1")

            if not row or row["id"] != id:
                return None

            card = dict(row)

            # Decrypt card number
            try:
                card["card_number"] = decrypt_password(card["card_number_encrypted"])
            except Exception as e:
                logger.error(f"Failed to decrypt card data: {e}")
                raise ValueError("Failed to decrypt card data")

            return PaymentCard(
                id=card["id"],
                card_holder_name=card["card_holder_name"],
                card_number=card.get("card_number"),
                expiry_month=card.get("expiry_month"),
                expiry_year=card.get("expiry_year"),
                created_at=card.get("created_at"),
                updated_at=card.get("updated_at"),
            )

    async def get(self) -> Optional[PaymentCard]:
        """
        Get the saved payment card with decrypted card number.

        Returns:
            PaymentCard entity or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM payment_card LIMIT 1")

            if not row:
                return None

            card = dict(row)

            # Decrypt card number
            try:
                card["card_number"] = decrypt_password(card["card_number_encrypted"])
            except Exception as e:
                logger.error(f"Failed to decrypt card data: {e}")
                raise ValueError("Failed to decrypt card data")

            return PaymentCard(
                id=card["id"],
                card_holder_name=card["card_holder_name"],
                card_number=card.get("card_number"),
                expiry_month=card.get("expiry_month"),
                expiry_year=card.get("expiry_year"),
                created_at=card.get("created_at"),
                updated_at=card.get("updated_at"),
            )

    async def get_masked(self) -> Optional[PaymentCard]:
        """
        Get the saved payment card with masked card number.

        Returns:
            PaymentCard entity or None if not found
        """
        async with self.db.get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM payment_card LIMIT 1")

            if not row:
                return None

            card = dict(row)

            # Decrypt card number to get last 4 digits, then mask
            try:
                card_number = decrypt_password(card["card_number_encrypted"])
                last_four = card_number[-4:]
                card["card_number_masked"] = f"**** **** **** {last_four}"
            except Exception as e:
                logger.error(f"Failed to decrypt card number: {e}")
                card["card_number_masked"] = "**** **** **** ****"

            return PaymentCard(
                id=card["id"],
                card_holder_name=card["card_holder_name"],
                card_number_masked=card.get("card_number_masked"),
                expiry_month=card.get("expiry_month"),
                expiry_year=card.get("expiry_year"),
                created_at=card.get("created_at"),
                updated_at=card.get("updated_at"),
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

    def _validate_card_data(self, data: Dict[str, Any]) -> None:
        """
        Validate payment card data using defensive validation (defense-in-depth).

        Validation rules:
        - Required fields: card_holder_name, card_number, expiry_month, expiry_year
        - Card number: Must be 13-19 digits (standard credit card length)
        - Expiry month: Must be 01-12 (two-digit format)

        Args:
            data: Card data to validate

        Raises:
            ValueError: If card data is invalid or missing required fields
        """
        required_fields = ["card_holder_name", "card_number", "expiry_month", "expiry_year"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Defensive validation (defense-in-depth)
        card_number = data["card_number"]
        expiry_month = data["expiry_month"]

        # Validate card_number: only digits, length 13-19
        if not card_number.isdigit() or not (13 <= len(card_number) <= 19):
            raise ValueError("Card number must be 13-19 digits")

        # Validate expiry_month: must be 01-12
        try:
            month = int(expiry_month)
        except ValueError:
            raise ValueError("Invalid expiry month format")

        if not (1 <= month <= 12):
            raise ValueError("Expiry month must be between 01 and 12")

    async def create(self, data: Dict[str, Any]) -> int:
        """
        Create or update payment card (upsert).

        Since only one payment card is stored at a time, this method
        updates the existing card if one exists, otherwise creates a new one.

        Args:
            data: Payment card data

        Returns:
            Card ID (existing or newly created)

        Raises:
            ValueError: If card data is invalid
        """
        return await self._upsert(data)

    async def update(self, data: Dict[str, Any]) -> int:
        """
        Update payment card (alias for create - maintains backward compatibility).

        Since only one payment card is stored at a time, this is functionally
        identical to create().

        Args:
            data: Payment card data

        Returns:
            Card ID

        Raises:
            ValueError: If card data is invalid
        """
        return await self._upsert(data)

    async def _upsert(self, data: Dict[str, Any]) -> int:
        """
        Internal method to create or update payment card.

        Args:
            data: Payment card data

        Returns:
            Card ID

        Raises:
            ValueError: If card data is invalid
        """
        # Validate card data
        self._validate_card_data(data)

        # Encrypt sensitive data (card number only)
        card_number_encrypted = encrypt_password(data["card_number"])

        async with self.db.get_connection() as conn:
            # Check if a card already exists
            existing = await conn.fetchrow("SELECT id FROM payment_card LIMIT 1")

            if existing:
                # Update existing card
                await conn.execute(
                    """
                    UPDATE payment_card
                    SET card_holder_name = $1,
                        card_number_encrypted = $2,
                        expiry_month = $3,
                        expiry_year = $4,
                        updated_at = NOW()
                    WHERE id = $5
                    """,
                    data["card_holder_name"],
                    card_number_encrypted,
                    data["expiry_month"],
                    data["expiry_year"],
                    existing["id"],
                )
                logger.info("Payment card updated")
                return int(existing["id"])
            else:
                # Insert new card
                card_id = await conn.fetchval(
                    """
                    INSERT INTO payment_card
                    (card_holder_name, card_number_encrypted, expiry_month,
                     expiry_year)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                    """,
                    data["card_holder_name"],
                    card_number_encrypted,
                    data["expiry_month"],
                    data["expiry_year"],
                )
                if card_id is None:
                    raise RuntimeError("Failed to get inserted card ID")
                logger.info(f"Payment card created with ID: {card_id}")
                return int(card_id)

    async def delete(self, id: int = 0) -> bool:
        """
        Delete payment card.

        Args:
            id: Card ID (not used as only one card exists)

        Returns:
            True if deleted, False otherwise
        """
        async with self.db.get_connection() as conn:
            existing = await conn.fetchrow("SELECT id FROM payment_card LIMIT 1")

            if not existing:
                return False

            await conn.execute("DELETE FROM payment_card WHERE id = $1", existing["id"])
            logger.info("Payment card deleted")
            return True
