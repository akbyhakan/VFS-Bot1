"""Mission processor for handling multi-country appointment requests."""

import random
from typing import TYPE_CHECKING, Any, Dict, List

from loguru import logger
from playwright.async_api import Page

from ...core.exceptions import VFSBotError
from ...utils.masking import mask_email
from .browser_manager import BrowserManager

if TYPE_CHECKING:
    from ...core.infra.runners import BotConfigDict
    from ...repositories import AppointmentRequestRepository
    from ...types.user import UserDict
    from ..notification import NotificationService
    from .booking_dependencies import BookingDependencies
    from .booking_executor import BookingExecutor
    from .reservation_builder import ReservationBuilder


class MissionProcessor:
    """Processes mission (country) appointment requests."""

    def __init__(
        self,
        config: "BotConfigDict",
        notifier: "NotificationService",
        deps: "BookingDependencies",
        appointment_request_repo: "AppointmentRequestRepository",
        reservation_builder: "ReservationBuilder",
        booking_executor: "BookingExecutor",
    ):
        """
        Initialize mission processor.

        Args:
            config: Bot configuration dictionary
            notifier: Notification service instance
            deps: BookingDependencies container with all required services
            appointment_request_repo: Appointment request repository instance
            reservation_builder: ReservationBuilder instance for building reservations
            booking_executor: BookingExecutor instance for executing bookings
        """
        self.config = config
        self.notifier = notifier
        self.deps = deps
        self.appointment_request_repo = appointment_request_repo
        self.reservation_builder = reservation_builder
        self.booking_executor = booking_executor

    async def process_normal_flow(self, page: Page, user: "UserDict", dedup_service: Any) -> None:
        """
        Process normal appointment flow (slot checking and booking) for ALL pending requests.

        This method handles multiple appointment requests across different countries and visa categories.
        For multi-mission scenarios, each country gets a separate browser instance (Chromium process).

        Args:
            page: Playwright page object (used only for backward compatibility with single-mission)
            user: User dictionary from database
            dedup_service: Deduplication service instance
        """
        # Step 1: Get ALL pending appointment requests
        appointment_requests = await self.appointment_request_repo.get_all_pending_for_user(
            user["id"]
        )

        if not appointment_requests:
            logger.info(f"No pending appointment requests for user {user['id']}")
            return

        logger.info(f"Found {len(appointment_requests)} pending request(s) for user {user['id']}")

        # Step 2: Group requests by country_code
        country_groups: Dict[str, List[Any]] = {}
        for request in appointment_requests:
            country_code = request.country_code
            if country_code not in country_groups:
                country_groups[country_code] = []
            country_groups[country_code].append(request)

        # Check if this is a simple single-mission case (backward compatibility)
        config_mission = self.config.get("vfs", {}).get("mission", "")
        is_single_mission = (
            len(country_groups) == 1
            and len(appointment_requests) == 1
            and list(country_groups.keys())[0] == config_mission
        )

        if is_single_mission:
            # Backward compatibility: use the provided page for single-mission scenarios
            logger.info(
                f"Single-mission scenario detected (country={config_mission}), "
                f"using provided page (no extra browser)"
            )
            country_code = list(country_groups.keys())[0]
            requests = country_groups[country_code]

            # Shuffle requests within the country group for anti-detection
            random.shuffle(requests)

            for request in requests:
                try:
                    await self.process_single_request(page, user, request, dedup_service)
                except Exception as e:
                    logger.error(
                        f"Error processing request #{request.id} for user {user['id']}: {e}"
                    )
                    continue
        else:
            # Multi-mission scenario: create separate browser instances per country
            logger.info(
                f"Multi-mission scenario detected with {len(country_groups)} country group(s)"
            )
            await self.process_multi_mission_flow(user, country_groups, dedup_service)

    async def process_multi_mission_flow(
        self, user: "UserDict", country_groups: Dict[str, List[Any]], dedup_service: Any
    ) -> None:
        """
        Process multiple appointment requests across different countries.

        Each country gets its own separate browser instance (Chromium process) for isolation
        and proper session management.

        Args:
            user: User dictionary from database
            country_groups: Dictionary mapping country_code to list of AppointmentRequest entities
            dedup_service: Deduplication service instance

        Raises:
            VFSBotError: If required managers are not available for multi-mission processing
        """
        # Validate that we have the necessary managers for creating browser instances
        if self.deps.infra.header_manager is None or self.deps.infra.proxy_manager is None:
            error_msg = (
                "Multi-mission processing requires header_manager and proxy_manager "
                "to create separate browser instances. These managers were not provided "
                "to BookingWorkflow constructor."
            )
            logger.error(error_msg)
            raise VFSBotError(error_msg, recoverable=False)

        # Step 1: Shuffle country order for anti-detection
        country_codes = list(country_groups.keys())
        random.shuffle(country_codes)

        logger.info(
            f"Processing {len(country_codes)} country group(s) in shuffled order: {country_codes}"
        )

        # Step 2: Process each country group with its own browser instance
        for country_code in country_codes:
            requests = country_groups[country_code]

            logger.info(f"Processing country {country_code}: {len(requests)} request(s)")

            # Create a NEW browser instance for this country
            country_browser = None
            country_page = None

            try:
                # Instantiate a new BrowserManager for this country
                country_browser = BrowserManager(
                    config=self.config,
                    header_manager=self.deps.infra.header_manager,
                    proxy_manager=self.deps.infra.proxy_manager,
                )

                logger.info(f"Starting new browser instance for country {country_code}")
                await country_browser.start()

                # Create a new page in the country-specific browser
                country_page = await country_browser.new_page()

                # Login to the mission-specific portal
                logger.info(f"Logging in to {country_code} portal for user {user['id']}")
                login_success = await self.deps.workflow.auth_service.login_for_mission(
                    country_page, user["email"], user["password"], country_code
                )

                if not login_success:
                    logger.error(f"Login failed for {country_code} portal, skipping country group")
                    continue

                # Shuffle requests within this country group for anti-detection
                random.shuffle(requests)

                logger.info(
                    f"Processing {len(requests)} request(s) for {country_code} in shuffled order"
                )

                # Process each request in the shuffled country group
                for request in requests:
                    try:
                        await self.process_single_request(
                            country_page, user, request, dedup_service
                        )
                    except Exception as e:
                        # Log error but continue with next request (error isolation)
                        logger.error(
                            f"Error processing request #{request.id} for country {country_code}: {e}"
                        )
                        continue

                logger.info(f"Completed processing country {country_code}")

            except Exception as e:
                # Log error but continue with next country (error isolation)
                logger.error(f"Error processing country {country_code} for user {user['id']}: {e}")
                continue

            finally:
                # Always clean up browser resources for this country
                if country_page:
                    try:
                        await country_page.close()
                        logger.debug(f"Closed page for country {country_code}")
                    except Exception as e:
                        logger.warning(f"Error closing page for {country_code}: {e}")

                if country_browser:
                    try:
                        await country_browser.close()
                        logger.info(f"Closed browser instance for country {country_code}")
                    except Exception as e:
                        logger.warning(f"Error closing browser for {country_code}: {e}")

    async def process_single_request(
        self, page: Page, user: "UserDict", appointment_request: Any, dedup_service: Any
    ) -> bool:
        """
        Process a single appointment request (slot checking and booking).

        This method returns a boolean indicating success/failure and propagates
        exceptions to the caller for error handling.

        Args:
            page: Playwright page object
            user: User dictionary from database
            appointment_request: AppointmentRequest entity
            dedup_service: Deduplication service instance

        Returns:
            True if slot was found and booking executed, False otherwise

        Raises:
            Exception: Any exception from booking flow is propagated to caller
        """
        # Extract criteria from AppointmentRequest
        person_count = appointment_request.person_count or len(appointment_request.persons or [])
        preferred_dates = appointment_request.preferred_dates or []
        centres = appointment_request.centres
        category = appointment_request.visa_category or user["category"]
        subcategory = appointment_request.visa_subcategory or user["subcategory"]

        logger.info(
            f"Processing AppointmentRequest #{appointment_request.id}: "
            f"country={appointment_request.country_code}, centres={centres}, "
            f"preferred_dates={preferred_dates}, person_count={person_count}, "
            f"category={category}/{subcategory}"
        )

        # Check centres sequentially (same page, SPA-safe)
        for centre in centres:
            centre = centre.strip()

            slot = await self.deps.workflow.slot_checker.check_slots(
                page,
                centre,
                category,
                subcategory,
                required_capacity=person_count,
                preferred_dates=preferred_dates,
            )

            if slot:
                await self.notifier.notify_slot_found(centre, slot["date"], slot["time"])
                logger.info(
                    f"Slot found for {person_count} person(s): "
                    f"{centre} - {slot['date']} {slot['time']}"
                )

                # Record slot pattern with country from AppointmentRequest
                await self.deps.workflow.slot_analyzer.record_slot_found_async(
                    country=appointment_request.country_code,
                    centre=centre,
                    category=category,
                    date=slot["date"],
                    time=slot["time"],
                )

                # Check for duplicate booking attempt
                is_duplicate = await dedup_service.is_duplicate(
                    user["id"], centre, category, slot["date"]
                )

                if is_duplicate:
                    logger.warning(
                        f"Skipping duplicate booking for user {user['id']}: "
                        f"{centre}/{category}/{slot['date']}"
                    )
                    continue

                # Build reservation directly from AppointmentRequest
                reservation = self.reservation_builder.build_reservation_from_request(
                    appointment_request.to_dict(), slot
                )

                if reservation:
                    await self.booking_executor.execute_and_confirm_booking(
                        page,
                        reservation,
                        user,
                        centre,
                        slot,
                        dedup_service,
                        category=category,
                        subcategory=subcategory,
                    )
                    return True

                break

        return False
