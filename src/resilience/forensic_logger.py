"""Country-aware forensic logging system for incident capture and analysis."""

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from playwright.async_api import Page

from src.constants import Resilience


class ForensicLogger:
    """Black box logging system with country-aware organization."""

    def __init__(
        self,
        base_dir: str = "logs/errors",
        country_code: str = "default",
        max_incidents: int = Resilience.FORENSIC_MAX_INCIDENTS,
        max_html_size: int = Resilience.FORENSIC_MAX_HTML_SIZE,
    ):
        """
        Initialize forensic logger with country-aware directory structure.

        Args:
            base_dir: Base directory for forensic logs
            country_code: Country code for organizing logs
            max_incidents: Maximum number of incidents to retain per country
            max_html_size: Maximum HTML dump size in bytes
        """
        self.base_dir = Path(base_dir)
        self.country_code = country_code.lower()
        self.max_incidents = max_incidents
        self.max_html_size = max_html_size

        # Create country-specific directory structure
        self.country_dir = self.base_dir / self.country_code
        self.country_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"🔒 Forensic logger initialized for country: {self.country_code} "
            f"(max incidents: {max_incidents})"
        )

    def _get_incident_dir(self, timestamp: datetime) -> Path:
        """
        Get incident directory path with date-based organization.

        Args:
            timestamp: Incident timestamp

        Returns:
            Path to incident directory (logs/errors/{country}/{YYYY-MM-DD}/)
        """
        date_str = timestamp.strftime("%Y-%m-%d")
        incident_dir = self.country_dir / date_str
        incident_dir.mkdir(parents=True, exist_ok=True)
        return incident_dir

    async def capture_incident(
        self,
        page: Page,
        error: Exception,
        context: Dict[str, Any],
        tried_selectors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Capture comprehensive incident data with screenshots and context.

        Args:
            page: Playwright page object
            error: Exception that occurred
            context: Additional context (action, step, etc.)
            tried_selectors: List of selectors that were tried

        Returns:
            Incident record with metadata and file paths
        """
        timestamp = datetime.now(timezone.utc)
        incident_id = timestamp.strftime("%Y%m%d_%H%M%S_%f")

        # Get incident directory
        incident_dir = self._get_incident_dir(timestamp)

        incident_record: Dict[str, Any] = {
            "id": incident_id,
            "timestamp": timestamp.isoformat(),
            "country_code": self.country_code,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "tried_selectors": tried_selectors or [],
            "captures": {},
        }

        try:
            # 1. Full-page screenshot
            screenshot_path = incident_dir / f"{incident_id}_screenshot.png"
            try:
                await page.screenshot(path=str(screenshot_path), full_page=True)
                incident_record["captures"]["screenshot"] = str(screenshot_path)
                logger.debug(f"📸 Captured screenshot: {screenshot_path.name}")
            except Exception as e:
                logger.warning(f"Failed to capture screenshot: {e}")

            # 2. Raw DOM dump
            dom_path = incident_dir / f"{incident_id}_dom.html"
            try:
                html_content = await page.content()

                # Truncate if exceeds max size
                if len(html_content) > self.max_html_size:
                    logger.warning(
                        f"HTML size {len(html_content)} exceeds max {self.max_html_size}, truncating"
                    )
                    html_content = html_content[: self.max_html_size]
                    html_content += "\n<!-- TRUNCATED -->"

                dom_path.write_text(html_content, encoding="utf-8", errors="replace")
                incident_record["captures"]["dom"] = str(dom_path)
                logger.debug(f"📄 Captured DOM: {dom_path.name}")
            except Exception as e:
                logger.warning(f"Failed to capture DOM: {e}")

            # 3. Context JSON with masked sensitive data
            context_path = incident_dir / f"{incident_id}_context.json"
            try:
                # Collect page metadata
                page_context = {
                    "url": page.url,
                    "title": await page.title(),
                    "viewport": page.viewport_size,
                    "user_agent": await page.evaluate("navigator.userAgent"),
                }

                # Collect and mask cookies
                try:
                    cookies = await page.context.cookies()
                    page_context["cookies"] = [
                        {
                            "name": c.get("name"),
                            "domain": c.get("domain"),
                            "path": c.get("path"),
                            "secure": c.get("secure"),
                            "httpOnly": c.get("httpOnly"),
                            "sameSite": c.get("sameSite"),
                            "value": "[MASKED]",  # Mask cookie values
                        }
                        for c in cookies
                    ]
                except Exception as e:
                    logger.debug(f"Could not capture cookies: {e}")
                    page_context["cookies"] = []

                # Collect and mask localStorage
                try:
                    local_storage = await page.evaluate("() => Object.keys(localStorage)")
                    page_context["localStorage"] = {
                        key: "[MASKED]" for key in local_storage
                    }  # Mask values
                except Exception as e:
                    logger.debug(f"Could not capture localStorage: {e}")
                    page_context["localStorage"] = {}

                # Collect and mask sessionStorage
                try:
                    session_storage = await page.evaluate("() => Object.keys(sessionStorage)")
                    page_context["sessionStorage"] = {
                        key: "[MASKED]" for key in session_storage
                    }  # Mask values
                except Exception as e:
                    logger.debug(f"Could not capture sessionStorage: {e}")
                    page_context["sessionStorage"] = {}

                # Add traceback
                page_context["traceback"] = traceback.format_exception(
                    type(error), error, error.__traceback__
                )

                # Combine all context
                full_context = {
                    **incident_record,
                    "page_context": page_context,
                }

                context_path.write_text(
                    json.dumps(full_context, indent=2, default=str), encoding="utf-8"
                )
                incident_record["captures"]["context"] = str(context_path)
                logger.debug(f"📋 Captured context: {context_path.name}")
            except Exception as e:
                logger.warning(f"Failed to capture context: {e}")

            logger.info(
                f"🔒 Forensic incident captured: {incident_id} "
                f"({self.country_code}, {incident_record['error_type']})"
            )

            # Cleanup old incidents if needed
            await self._cleanup_old_incidents()

            return incident_record

        except Exception as e:
            logger.error(f"Failed to capture forensic incident: {e}")
            # Return partial record even if capture failed
            return incident_record

    async def _cleanup_old_incidents(self) -> None:
        """Remove oldest incidents if count exceeds max_incidents."""
        try:
            # Get all incident context files across all dates
            context_files = list(self.country_dir.glob("*/*_context.json"))

            if len(context_files) > self.max_incidents:
                # Sort by modification time (oldest first)
                context_files.sort(key=lambda p: p.stat().st_mtime)

                # Calculate how many to delete
                to_delete = len(context_files) - self.max_incidents

                for context_file in context_files[:to_delete]:
                    # Delete all related files for this incident
                    incident_id = context_file.stem.replace("_context", "")
                    incident_dir = context_file.parent

                    # Delete screenshot, DOM, and context
                    for suffix in ["_screenshot.png", "_dom.html", "_context.json"]:
                        file_path = incident_dir / f"{incident_id}{suffix}"
                        if file_path.exists():
                            file_path.unlink()

                logger.info(f"🧹 Cleaned up {to_delete} old forensic incidents for {self.country_code}")

        except Exception as e:
            logger.warning(f"Failed to cleanup old incidents: {e}")

    def get_recent_incidents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent incidents for this country.

        Args:
            limit: Maximum number of incidents to return

        Returns:
            List of incident records sorted by timestamp (newest first)
        """
        try:
            # Get all context files
            context_files = list(self.country_dir.glob("*/*_context.json"))

            # Sort by modification time (newest first)
            context_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            incidents = []
            for context_file in context_files[:limit]:
                try:
                    with open(context_file, "r", encoding="utf-8") as f:
                        incident = json.load(f)
                        incidents.append(incident)
                except Exception as e:
                    logger.warning(f"Failed to load incident {context_file}: {e}")

            return incidents

        except Exception as e:
            logger.error(f"Failed to get recent incidents: {e}")
            return []

    def get_incident_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific incident by ID.

        Args:
            incident_id: Incident ID to retrieve

        Returns:
            Incident record or None if not found
        """
        try:
            # Search for context file across all dates
            context_files = list(self.country_dir.glob(f"*/{incident_id}_context.json"))

            if context_files:
                context_file = context_files[0]
                with open(context_file, "r", encoding="utf-8") as f:
                    return json.load(f)

            logger.warning(f"Incident not found: {incident_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get incident {incident_id}: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """
        Get forensic logger status.

        Returns:
            Status dictionary with metrics
        """
        try:
            context_files = list(self.country_dir.glob("*/*_context.json"))

            return {
                "country_code": self.country_code,
                "total_incidents": len(context_files),
                "max_incidents": self.max_incidents,
                "base_dir": str(self.base_dir),
                "country_dir": str(self.country_dir),
            }

        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {
                "country_code": self.country_code,
                "error": str(e),
            }
