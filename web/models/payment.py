"""Payment models for VFS-Bot web application."""

from pydantic import BaseModel, Field, field_validator


class PaymentCardRequest(BaseModel):
    """Payment card request model.

    Note: CVV is NOT stored per PCI-DSS Requirement 3.2.
    """

    card_holder_name: str = Field(..., min_length=2, max_length=100)
    card_number: str = Field(..., min_length=13, max_length=19, pattern=r"^\d{13,19}$")
    expiry_month: str = Field(..., pattern=r"^(0[1-9]|1[0-2])$")
    expiry_year: str = Field(..., pattern=r"^\d{2,4}$")

    @field_validator("card_number")
    @classmethod
    def validate_luhn(cls, v: str) -> str:
        """Validate card number using Luhn algorithm."""
        # Luhn algorithm implementation
        total = 0
        is_even = False

        for i in range(len(v) - 1, -1, -1):
            digit = int(v[i])

            if is_even:
                digit *= 2
                if digit > 9:
                    digit -= 9

            total += digit
            is_even = not is_even

        if total % 10 != 0:
            raise ValueError("Invalid card number (failed Luhn check)")

        return v

    @field_validator("card_holder_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate card holder name contains only letters and spaces."""
        trimmed = v.strip()
        # Allow letters (including Turkish characters) and spaces only
        if not all(c.isalpha() or c.isspace() for c in trimmed):
            raise ValueError("Card holder name must contain only letters and spaces")
        return trimmed


class PaymentCardResponse(BaseModel):
    """Payment card response model (masked)."""

    id: int
    card_holder_name: str
    card_number_masked: str
    expiry_month: str
    expiry_year: str
    created_at: str

