"""Message templates for NotificationService — separates formatting from transport."""


class NotificationTemplates:
    """Static message templates for each notification event type."""

    @staticmethod
    def slot_found(centre: str, date: str, time: str) -> tuple[str, str]:
        """Template for appointment slot found event."""
        title = "🎉 Appointment Slot Found!"
        message = f"""
Centre: {centre}
Date: {date}
Time: {time}

The bot is proceeding with the booking.
"""
        return title, message

    @staticmethod
    def booking_success(centre: str, date: str, time: str, reference: str) -> tuple[str, str]:
        """Template for successful booking event."""
        title = "✅ Appointment Booked Successfully!"
        message = f"""
Centre: {centre}
Date: {date}
Time: {time}
Reference: {reference}

Your appointment has been successfully booked!
"""
        return title, message

    @staticmethod
    def error(error_type: str, details: str) -> tuple[str, str]:
        """Template for error event."""
        title = f"❌ Error: {error_type}"
        message = f"""
An error occurred during bot execution:

{details}

The bot will retry automatically.
"""
        return title, message

    @staticmethod
    def bot_started() -> tuple[str, str]:
        """Template for bot started event."""
        return "🚀 VFS-Bot Started", "The bot has started checking for appointment slots."

    @staticmethod
    def bot_stopped() -> tuple[str, str]:
        """Template for bot stopped event."""
        return "🛑 VFS-Bot Stopped", "The bot has been stopped."

    @staticmethod
    def waitlist_success(details: dict, timezone_name: str = "Europe/Istanbul") -> tuple[str, str]:
        """Template for waitlist registration success event."""
        from src.utils.helpers import format_local_datetime

        # Build people list
        people_list = ""
        people = details.get("people", [])
        if people:
            for i, person in enumerate(people, 1):
                people_list += f"   {i}. {person}\n"
        else:
            people_list = "   (Information unavailable)\n"

        dt_str = format_local_datetime(tz_name=timezone_name)

        title = "✅ BEKLEME LİSTESİNE KAYIT BAŞARILI!"
        message = f"""
📧 Giriş Yapılan Hesap: {details.get('login_email', 'N/A')}
📋 Referans: {details.get('reference_number', 'N/A')}

👥 Kayıt Yapılan Kişiler:
{people_list}
🌍 Ülke: {details.get('country', 'N/A')}
📍 Merkez: {details.get('centre', 'N/A')}
📂 Kategori: {details.get('category', 'N/A')}
📁 Alt Kategori: {details.get('subcategory', 'N/A')}

💰 Toplam Ücret: {details.get('total_amount', 'N/A')}

📅 Tarih: {dt_str}

ℹ️ Bekleme listesi durumunuz güncellendiğinde bilgilendirileceksiniz.
"""
        return title, message
