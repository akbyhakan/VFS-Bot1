"""Core constants used across the application."""

# Allowed fields for personal_details table (SQL injection prevention)
ALLOWED_PERSONAL_DETAILS_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "passport_number",
        "passport_expiry",
        "gender",
        "mobile_code",
        "mobile_number",
        "email",
        "nationality",
        "date_of_birth",
        "address_line1",
        "address_line2",
        "state",
        "city",
        "postcode",
    }
)

# Allowed fields for users table update (SQL injection prevention)
ALLOWED_USER_UPDATE_FIELDS = frozenset(
    {
        "email",
        "password",
        "centre",
        "category",
        "subcategory",
        "active",
    }
)
