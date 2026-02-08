"""Common shared models for VFS-Bot web application."""

from pydantic import BaseModel


class WebhookUrlsResponse(BaseModel):
    """Webhook URLs response model."""

    appointment_webhook: str
    payment_webhook: str
    base_url: str


class CountryResponse(BaseModel):
    """Country response model."""

    code: str
    name_en: str
    name_tr: str
