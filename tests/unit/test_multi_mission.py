"""Tests for multi-mission support (multiple appointment requests across countries)."""

import random
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet

from src.models.database import Database
from src.repositories.appointment_request_repository import AppointmentRequest
from src.utils.encryption import reset_encryption


@pytest.fixture(scope="function")
def unique_encryption_key(monkeypatch):
    """Set up unique encryption key for each test and reset global encryption instance."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    # Reset global encryption instance to ensure it uses the new key
    reset_encryption()
    yield key
    # Cleanup: reset encryption instance after test
    reset_encryption()


@pytest_asyncio.fixture
async def test_db(tmp_path, unique_encryption_key):
    """Create a test database."""
    from src.constants import Database as DatabaseConfig

    # Use PostgreSQL test database URL
    test_db_url = DatabaseConfig.TEST_URL
    db = Database(database_url=test_db_url)

    try:
        await db.connect()
    except Exception as e:
        pytest.skip(f"PostgreSQL test database not available: {e}")

    yield db
    await db.close()


@pytest.fixture
def mock_appointment_requests():
    """Create mock appointment requests for different countries and categories."""
    return [
        AppointmentRequest(
            id=1,
            country_code="fra",
            visa_category="Tourism",
            visa_subcategory="Short Stay",
            centres=["Istanbul"],
            preferred_dates=["15/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T10:00:00Z",
            persons=[{"email": "test@example.com", "first_name": "Test"}],
        ),
        AppointmentRequest(
            id=2,
            country_code="fra",
            visa_category="Business",
            visa_subcategory="Short Stay",
            centres=["Istanbul"],
            preferred_dates=["16/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T11:00:00Z",
            persons=[{"email": "test@example.com", "first_name": "Test"}],
        ),
        AppointmentRequest(
            id=3,
            country_code="bgr",
            visa_category="Tourism",
            visa_subcategory="Short Stay",
            centres=["Ankara"],
            preferred_dates=["17/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T12:00:00Z",
            persons=[{"email": "test@example.com", "first_name": "Test"}],
        ),
    ]


@pytest.mark.asyncio
async def test_get_all_pending_for_user_multiple_requests(test_db):
    """Test get_all_pending_for_user returns all pending requests."""
    from src.repositories import AppointmentRequestRepository, UserRepository

    user_repo = UserRepository(test_db)
    request_repo = AppointmentRequestRepository(test_db)

    # Create user
    user_id = await user_repo.create(
        {
            "email": "multi@example.com",
            "password": "password123",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    # Create 3 pending requests
    persons = [
        {
            "first_name": "Test",
            "last_name": "User",
            "gender": "male",
            "nationality": "Turkey",
            "birth_date": "15/01/1990",
            "passport_number": "U12345678",
            "passport_issue_date": "01/01/2020",
            "passport_expiry_date": "01/01/2030",
            "phone_code": "90",
            "phone_number": "5551234567",
            "email": "multi@example.com",
            "is_child_with_parent": False,
        }
    ]

    req_id_1 = await test_db.create_appointment_request(
        country_code="fra",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["15/02/2026"],
        person_count=1,
        persons=persons,
    )

    req_id_2 = await test_db.create_appointment_request(
        country_code="fra",
        visa_category="Business",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["16/02/2026"],
        person_count=1,
        persons=persons,
    )

    req_id_3 = await test_db.create_appointment_request(
        country_code="bgr",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Ankara"],
        preferred_dates=["17/02/2026"],
        person_count=1,
        persons=persons,
    )

    # Get all pending requests
    requests = await request_repo.get_all_pending_for_user(user_id)

    # Should return all 3 requests
    assert len(requests) == 3
    request_ids = {req.id for req in requests}
    assert req_id_1 in request_ids
    assert req_id_2 in request_ids
    assert req_id_3 in request_ids


@pytest.mark.asyncio
async def test_get_all_pending_for_user_no_requests(test_db):
    """Test get_all_pending_for_user returns empty list when no requests."""
    from src.repositories import AppointmentRequestRepository, UserRepository

    user_repo = UserRepository(test_db)
    request_repo = AppointmentRequestRepository(test_db)

    # Create user with no requests
    user_id = await user_repo.create(
        {
            "email": "noRequests@example.com",
            "password": "password123",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    # Get all pending requests
    requests = await request_repo.get_all_pending_for_user(user_id)

    # Should return empty list
    assert requests == []


@pytest.mark.asyncio
async def test_get_all_pending_for_user_only_pending(test_db):
    """Test get_all_pending_for_user returns only pending requests, not completed."""
    from src.repositories import AppointmentRequestRepository, UserRepository

    user_repo = UserRepository(test_db)
    request_repo = AppointmentRequestRepository(test_db)

    # Create user
    user_id = await user_repo.create(
        {
            "email": "filtered@example.com",
            "password": "password123",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    persons = [
        {
            "first_name": "Test",
            "last_name": "User",
            "gender": "male",
            "nationality": "Turkey",
            "birth_date": "15/01/1990",
            "passport_number": "U12345678",
            "passport_issue_date": "01/01/2020",
            "passport_expiry_date": "01/01/2030",
            "phone_code": "90",
            "phone_number": "5551234567",
            "email": "filtered@example.com",
            "is_child_with_parent": False,
        }
    ]

    # Create 2 pending and 1 completed request
    req_id_1 = await test_db.create_appointment_request(
        country_code="fra",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["15/02/2026"],
        person_count=1,
        persons=persons,
    )

    req_id_2 = await test_db.create_appointment_request(
        country_code="bgr",
        visa_category="Business",
        visa_subcategory="Short Stay",
        centres=["Ankara"],
        preferred_dates=["16/02/2026"],
        person_count=1,
        persons=persons,
    )

    # Mark one as completed
    await request_repo.update_status(req_id_2, "completed")

    # Get all pending requests
    requests = await request_repo.get_all_pending_for_user(user_id)

    # Should return only the pending request
    assert len(requests) == 1
    assert requests[0].id == req_id_1


@pytest.mark.asyncio
async def test_backward_compatibility_get_pending_for_user(test_db):
    """Test that get_pending_for_user still works (backward compatibility)."""
    from src.repositories import AppointmentRequestRepository, UserRepository

    user_repo = UserRepository(test_db)
    request_repo = AppointmentRequestRepository(test_db)

    # Create user
    user_id = await user_repo.create(
        {
            "email": "backward@example.com",
            "password": "password123",
            "center_name": "Istanbul",
            "visa_category": "Tourism",
            "visa_subcategory": "Short Stay",
        }
    )

    persons = [
        {
            "first_name": "Test",
            "last_name": "User",
            "gender": "male",
            "nationality": "Turkey",
            "birth_date": "15/01/1990",
            "passport_number": "U12345678",
            "passport_issue_date": "01/01/2020",
            "passport_expiry_date": "01/01/2030",
            "phone_code": "90",
            "phone_number": "5551234567",
            "email": "backward@example.com",
            "is_child_with_parent": False,
        }
    ]

    # Create 3 requests
    await test_db.create_appointment_request(
        country_code="fra",
        visa_category="Tourism",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["15/02/2026"],
        person_count=1,
        persons=persons,
    )

    req_id_2 = await test_db.create_appointment_request(
        country_code="fra",
        visa_category="Business",
        visa_subcategory="Short Stay",
        centres=["Istanbul"],
        preferred_dates=["16/02/2026"],
        person_count=1,
        persons=persons,
    )

    # Old method should still return only the most recent one
    request = await request_repo.get_pending_for_user(user_id)

    # Should return most recent (req_id_2)
    assert request is not None
    assert request.id == req_id_2


@pytest.mark.asyncio
async def test_login_for_mission():
    """Test login_for_mission accepts mission_code parameter and calls login with correct URL."""
    from src.services.bot.auth_service import AuthService

    config = {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tr",
            "language": "en",
            "mission": "fra",
        }
    }

    captcha_solver = MagicMock()
    auth_service = AuthService(config, captcha_solver)

    # Mock page
    page = AsyncMock()

    # We'll verify that safe_navigate is called with the correct URL for the mission
    with patch("src.services.bot.auth_service.safe_navigate") as mock_navigate:
        mock_navigate.return_value = True
        
        with patch.object(auth_service, 'handle_otp_verification', return_value=True):
            with patch("src.services.bot.auth_service.smart_fill"):
                with patch("src.services.bot.auth_service.smart_click"):
                    # Mock successful login detection
                    page.locator = MagicMock()
                    page.locator.return_value.count = AsyncMock(side_effect=[0, 0, 1])
                    page.wait_for_load_state = AsyncMock()
                    page.get_attribute = AsyncMock(return_value=None)

                    result = await auth_service.login_for_mission(
                        page, "test@example.com", "password", "bgr"
                    )

                    # Verify safe_navigate was called with bgr mission URL
                    mock_navigate.assert_called_once()
                    called_url = mock_navigate.call_args[0][1]
                    assert "bgr" in called_url
                    assert called_url == "https://visa.vfsglobal.com/tr/en/bgr/login"
                    assert result is True


@pytest.mark.asyncio
async def test_login_backward_compatibility():
    """Test login() still works and uses config mission (backward compatibility)."""
    from src.services.bot.auth_service import AuthService

    config = {
        "vfs": {
            "base_url": "https://visa.vfsglobal.com",
            "country": "tr",
            "language": "en",
            "mission": "fra",
        }
    }

    captcha_solver = MagicMock()
    auth_service = AuthService(config, captcha_solver)

    # Mock page
    page = AsyncMock()
    page.locator.return_value.count = AsyncMock(return_value=0)
    page.wait_for_load_state = AsyncMock()

    # Mock login_for_mission to verify it's called with config mission
    auth_service.login_for_mission = AsyncMock(return_value=True)

    result = await auth_service.login(page, "test@example.com", "password")

    # Verify login_for_mission was called with mission from config
    auth_service.login_for_mission.assert_called_once_with(
        page, "test@example.com", "password", "fra"
    )
    assert result is True


def test_country_grouping_logic(mock_appointment_requests):
    """Test that requests are correctly grouped by country_code."""
    # Group by country
    country_groups: Dict[str, List[Any]] = {}
    for request in mock_appointment_requests:
        country_code = request.country_code
        if country_code not in country_groups:
            country_groups[country_code] = []
        country_groups[country_code].append(request)

    # Verify grouping
    assert len(country_groups) == 2  # fra and bgr
    assert len(country_groups["fra"]) == 2  # Tourism and Business
    assert len(country_groups["bgr"]) == 1  # Tourism only

    # Verify correct requests in each group
    fra_categories = {req.visa_category for req in country_groups["fra"]}
    assert fra_categories == {"Tourism", "Business"}

    bgr_categories = {req.visa_category for req in country_groups["bgr"]}
    assert bgr_categories == {"Tourism"}


def test_shuffle_behavior():
    """Test that shuffle randomizes order (probabilistic test)."""
    items = list(range(10))
    original = items.copy()

    # Shuffle multiple times and verify at least one produces different order
    different_count = 0
    for _ in range(10):
        shuffled = items.copy()
        random.shuffle(shuffled)
        if shuffled != original:
            different_count += 1

    # With 10 items and 10 trials, we should get at least one different order
    # (probability of all being same is essentially 0)
    assert different_count > 0


@pytest.mark.asyncio
async def test_process_normal_flow_multiple_requests():
    """Test _process_normal_flow handles multiple requests with grouping and shuffling."""
    from src.services.bot.booking_workflow import BookingWorkflow

    # Mock dependencies
    db = MagicMock()
    config = {
        "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tr", "mission": "fra"}
    }
    auth_service = MagicMock()
    slot_checker = MagicMock()
    booking_service = MagicMock()
    notifier = MagicMock()
    human_sim = MagicMock()
    waitlist_handler = MagicMock()
    error_handler = MagicMock()
    slot_analyzer = MagicMock()
    session_recovery = MagicMock()
    page_state_detector = MagicMock()

    workflow = BookingWorkflow(
        config=config,
        db=db,
        notifier=notifier,
        auth_service=auth_service,
        slot_checker=slot_checker,
        booking_service=booking_service,
        waitlist_handler=waitlist_handler,
        error_handler=error_handler,
        slot_analyzer=slot_analyzer,
        session_recovery=session_recovery,
        page_state_detector=page_state_detector,
        human_sim=human_sim,
    )

    # Mock get_all_pending_for_user to return 3 requests
    mock_requests = [
        AppointmentRequest(
            id=1,
            country_code="fra",
            visa_category="Tourism",
            visa_subcategory="Short Stay",
            centres=["Istanbul"],
            preferred_dates=["15/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T10:00:00Z",
            persons=[],
        ),
        AppointmentRequest(
            id=2,
            country_code="fra",
            visa_category="Business",
            visa_subcategory="Short Stay",
            centres=["Istanbul"],
            preferred_dates=["16/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T11:00:00Z",
            persons=[],
        ),
        AppointmentRequest(
            id=3,
            country_code="bgr",
            visa_category="Tourism",
            visa_subcategory="Short Stay",
            centres=["Ankara"],
            preferred_dates=["17/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T12:00:00Z",
            persons=[],
        ),
    ]

    workflow.appointment_request_repo.get_all_pending_for_user = AsyncMock(
        return_value=mock_requests
    )
    workflow._process_single_request = AsyncMock()

    # Mock user
    user = {
        "id": 1,
        "email": "test@example.com",
        "category": "Tourism",
        "subcategory": "Short Stay",
    }

    # Mock page and dedup service
    page = AsyncMock()
    dedup_service = MagicMock()

    # Run the method
    await workflow._process_normal_flow(page, user, dedup_service)

    # Verify _process_single_request was called 3 times (once per request)
    assert workflow._process_single_request.call_count == 3

    # Verify all requests were processed
    processed_request_ids = {
        call.args[2].id for call in workflow._process_single_request.call_args_list
    }
    assert processed_request_ids == {1, 2, 3}


@pytest.mark.asyncio
async def test_process_normal_flow_error_isolation():
    """Test that errors in one request don't stop processing of others."""
    from src.services.bot.booking_workflow import BookingWorkflow

    # Mock dependencies
    db = MagicMock()
    config = {
        "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tr", "mission": "fra"}
    }
    auth_service = MagicMock()
    slot_checker = MagicMock()
    booking_service = MagicMock()
    notifier = MagicMock()
    human_sim = MagicMock()
    waitlist_handler = MagicMock()
    error_handler = MagicMock()
    slot_analyzer = MagicMock()
    session_recovery = MagicMock()
    page_state_detector = MagicMock()

    workflow = BookingWorkflow(
        config=config,
        db=db,
        notifier=notifier,
        auth_service=auth_service,
        slot_checker=slot_checker,
        booking_service=booking_service,
        waitlist_handler=waitlist_handler,
        error_handler=error_handler,
        slot_analyzer=slot_analyzer,
        session_recovery=session_recovery,
        page_state_detector=page_state_detector,
        human_sim=human_sim,
    )

    # Mock get_all_pending_for_user to return 3 requests
    mock_requests = [
        AppointmentRequest(
            id=1,
            country_code="fra",
            visa_category="Tourism",
            visa_subcategory="Short Stay",
            centres=["Istanbul"],
            preferred_dates=["15/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T10:00:00Z",
            persons=[],
        ),
        AppointmentRequest(
            id=2,
            country_code="fra",
            visa_category="Business",
            visa_subcategory="Short Stay",
            centres=["Istanbul"],
            preferred_dates=["16/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T11:00:00Z",
            persons=[],
        ),
        AppointmentRequest(
            id=3,
            country_code="bgr",
            visa_category="Tourism",
            visa_subcategory="Short Stay",
            centres=["Ankara"],
            preferred_dates=["17/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T12:00:00Z",
            persons=[],
        ),
    ]

    workflow.appointment_request_repo.get_all_pending_for_user = AsyncMock(
        return_value=mock_requests
    )

    # Make second request fail
    async def process_with_error(page, user, request, dedup):
        if request.id == 2:
            raise Exception("Simulated error for request 2")

    workflow._process_single_request = AsyncMock(side_effect=process_with_error)

    # Mock user
    user = {
        "id": 1,
        "email": "test@example.com",
        "category": "Tourism",
        "subcategory": "Short Stay",
    }

    # Mock page and dedup service
    page = AsyncMock()
    dedup_service = MagicMock()

    # Run the method - should not raise even though request 2 fails
    await workflow._process_normal_flow(page, user, dedup_service)

    # Verify all 3 requests were attempted
    assert workflow._process_single_request.call_count == 3


@pytest.mark.asyncio
async def test_multi_mission_creates_separate_browsers():
    """Test that multi-mission flow creates separate browser instances for each country."""
    from src.services.bot.booking_workflow import BookingWorkflow

    # Mock dependencies
    db = MagicMock()
    config = {
        "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tr", "mission": "fra"}
    }
    auth_service = MagicMock()
    auth_service.login_for_mission = AsyncMock(return_value=True)
    
    slot_checker = MagicMock()
    booking_service = MagicMock()
    notifier = MagicMock()
    human_sim = MagicMock()
    waitlist_handler = MagicMock()
    error_handler = MagicMock()
    slot_analyzer = MagicMock()
    session_recovery = MagicMock()
    page_state_detector = MagicMock()
    header_manager = MagicMock()
    proxy_manager = MagicMock()

    workflow = BookingWorkflow(
        config=config,
        db=db,
        notifier=notifier,
        auth_service=auth_service,
        slot_checker=slot_checker,
        booking_service=booking_service,
        waitlist_handler=waitlist_handler,
        error_handler=error_handler,
        slot_analyzer=slot_analyzer,
        session_recovery=session_recovery,
        page_state_detector=page_state_detector,
        human_sim=human_sim,
        header_manager=header_manager,
        proxy_manager=proxy_manager,
    )

    # Mock get_all_pending_for_user to return 2 requests for different countries
    mock_requests = [
        AppointmentRequest(
            id=1,
            country_code="fra",
            visa_category="Tourism",
            visa_subcategory="Short Stay",
            centres=["Istanbul"],
            preferred_dates=["15/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T10:00:00Z",
            persons=[],
        ),
        AppointmentRequest(
            id=2,
            country_code="bgr",
            visa_category="Tourism",
            visa_subcategory="Short Stay",
            centres=["Ankara"],
            preferred_dates=["17/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T12:00:00Z",
            persons=[],
        ),
    ]

    workflow.appointment_request_repo.get_all_pending_for_user = AsyncMock(
        return_value=mock_requests
    )
    workflow._process_single_request = AsyncMock()

    # Mock user
    user = {
        "id": 1,
        "email": "test@example.com",
        "password": "password",
        "category": "Tourism",
        "subcategory": "Short Stay",
    }

    # Mock page and dedup service
    page = AsyncMock()
    dedup_service = MagicMock()

    # Mock BrowserManager to track browser instances
    browser_instances_created = []
    
    async def mock_browser_start(self):
        """Mock start method that tracks this instance."""
        browser_instances_created.append(self)
    
    async def mock_browser_close(self):
        """Mock close method."""
        pass
    
    async def mock_new_page(self):
        """Mock new_page method."""
        return AsyncMock()

    with patch("src.services.bot.booking_workflow.BrowserManager") as MockBrowserManager:
        # Configure mock to create instances and track calls
        def create_browser_instance(*args, **kwargs):
            mock_browser = MagicMock()
            mock_browser.start = AsyncMock(side_effect=lambda: mock_browser_start(mock_browser))
            mock_browser.close = AsyncMock(side_effect=lambda: mock_browser_close(mock_browser))
            mock_browser.new_page = AsyncMock(side_effect=lambda: mock_new_page(mock_browser))
            return mock_browser
        
        MockBrowserManager.side_effect = create_browser_instance

        # Run the method
        await workflow._process_normal_flow(page, user, dedup_service)

        # Verify 2 separate BrowserManager instances were created (one per country)
        assert MockBrowserManager.call_count == 2
        
        # Verify both browsers were started and closed
        assert len(browser_instances_created) == 2
        for browser in browser_instances_created:
            browser.start.assert_called_once()
            browser.close.assert_called_once()
            browser.new_page.assert_called_once()


@pytest.mark.asyncio
async def test_single_mission_uses_original_page():
    """Test that single-mission scenario uses the provided page (backward compatibility)."""
    from src.services.bot.booking_workflow import BookingWorkflow

    # Mock dependencies
    db = MagicMock()
    config = {
        "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tr", "mission": "fra"}
    }
    auth_service = MagicMock()
    slot_checker = MagicMock()
    booking_service = MagicMock()
    notifier = MagicMock()
    human_sim = MagicMock()
    waitlist_handler = MagicMock()
    error_handler = MagicMock()
    slot_analyzer = MagicMock()
    session_recovery = MagicMock()
    page_state_detector = MagicMock()

    workflow = BookingWorkflow(
        config=config,
        db=db,
        notifier=notifier,
        auth_service=auth_service,
        slot_checker=slot_checker,
        booking_service=booking_service,
        waitlist_handler=waitlist_handler,
        error_handler=error_handler,
        slot_analyzer=slot_analyzer,
        session_recovery=session_recovery,
        page_state_detector=page_state_detector,
        human_sim=human_sim,
    )

    # Mock get_all_pending_for_user to return 1 request matching config mission
    mock_requests = [
        AppointmentRequest(
            id=1,
            country_code="fra",  # Matches config mission
            visa_category="Tourism",
            visa_subcategory="Short Stay",
            centres=["Istanbul"],
            preferred_dates=["15/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T10:00:00Z",
            persons=[],
        ),
    ]

    workflow.appointment_request_repo.get_all_pending_for_user = AsyncMock(
        return_value=mock_requests
    )
    workflow._process_single_request = AsyncMock()

    # Mock user
    user = {
        "id": 1,
        "email": "test@example.com",
        "category": "Tourism",
        "subcategory": "Short Stay",
    }

    # Mock page and dedup service
    page = AsyncMock()
    dedup_service = MagicMock()

    # Mock BrowserManager to verify it's NOT instantiated
    with patch("src.services.bot.booking_workflow.BrowserManager") as MockBrowserManager:
        # Run the method
        await workflow._process_normal_flow(page, user, dedup_service)

        # Verify NO new BrowserManager instances were created (backward compatible)
        MockBrowserManager.assert_not_called()
        
        # Verify _process_single_request was called with the original page
        workflow._process_single_request.assert_called_once()
        call_args = workflow._process_single_request.call_args
        assert call_args[0][0] == page  # First arg should be the original page


@pytest.mark.asyncio
async def test_browser_cleanup_on_error():
    """Test that browser instances are properly cleaned up even when errors occur."""
    from src.services.bot.booking_workflow import BookingWorkflow

    # Mock dependencies
    db = MagicMock()
    config = {
        "vfs": {"base_url": "https://visa.vfsglobal.com", "country": "tr", "mission": "fra"}
    }
    auth_service = MagicMock()
    # Simulate login failure for one country
    auth_service.login_for_mission = AsyncMock(side_effect=[False, True])
    
    slot_checker = MagicMock()
    booking_service = MagicMock()
    notifier = MagicMock()
    human_sim = MagicMock()
    waitlist_handler = MagicMock()
    error_handler = MagicMock()
    slot_analyzer = MagicMock()
    session_recovery = MagicMock()
    page_state_detector = MagicMock()
    header_manager = MagicMock()
    proxy_manager = MagicMock()

    workflow = BookingWorkflow(
        config=config,
        db=db,
        notifier=notifier,
        auth_service=auth_service,
        slot_checker=slot_checker,
        booking_service=booking_service,
        waitlist_handler=waitlist_handler,
        error_handler=error_handler,
        slot_analyzer=slot_analyzer,
        session_recovery=session_recovery,
        page_state_detector=page_state_detector,
        human_sim=human_sim,
        header_manager=header_manager,
        proxy_manager=proxy_manager,
    )

    # Mock get_all_pending_for_user to return 2 requests for different countries
    mock_requests = [
        AppointmentRequest(
            id=1,
            country_code="fra",
            visa_category="Tourism",
            visa_subcategory="Short Stay",
            centres=["Istanbul"],
            preferred_dates=["15/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T10:00:00Z",
            persons=[],
        ),
        AppointmentRequest(
            id=2,
            country_code="bgr",
            visa_category="Tourism",
            visa_subcategory="Short Stay",
            centres=["Ankara"],
            preferred_dates=["17/02/2026"],
            person_count=1,
            status="pending",
            created_at="2026-02-10T12:00:00Z",
            persons=[],
        ),
    ]

    workflow.appointment_request_repo.get_all_pending_for_user = AsyncMock(
        return_value=mock_requests
    )
    workflow._process_single_request = AsyncMock()

    # Mock user
    user = {
        "id": 1,
        "email": "test@example.com",
        "password": "password",
        "category": "Tourism",
        "subcategory": "Short Stay",
    }

    # Mock page and dedup service
    page = AsyncMock()
    dedup_service = MagicMock()

    # Track browser cleanup
    browser_close_calls = []
    page_close_calls = []
    
    with patch("src.services.bot.booking_workflow.BrowserManager") as MockBrowserManager:
        def create_browser_instance(*args, **kwargs):
            mock_browser = MagicMock()
            mock_browser.start = AsyncMock()
            
            async def track_close():
                browser_close_calls.append(mock_browser)
            
            mock_browser.close = AsyncMock(side_effect=track_close)
            
            mock_page = AsyncMock()
            
            async def track_page_close():
                page_close_calls.append(mock_page)
                
            mock_page.close = AsyncMock(side_effect=track_page_close)
            mock_browser.new_page = AsyncMock(return_value=mock_page)
            return mock_browser
        
        MockBrowserManager.side_effect = create_browser_instance

        # Run the method
        await workflow._process_normal_flow(page, user, dedup_service)

        # Verify 2 browsers were created
        assert MockBrowserManager.call_count == 2
        
        # Verify both browsers were closed (even though first login failed)
        assert len(browser_close_calls) == 2
        
        # Verify both pages were closed
        assert len(page_close_calls) == 2
