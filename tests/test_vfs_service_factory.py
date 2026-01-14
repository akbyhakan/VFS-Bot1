"""Tests for VFS service factory."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from src.models.user import User, UserRole, UserSettings
from src.services.vfs_service_factory import VFSServiceFactory
from src.services.vfs_api_client import VFSApiClient
from src.services.captcha_solver import CaptchaSolver


@pytest.fixture
def mock_captcha_solver():
    """Create a mock captcha solver."""
    return CaptchaSolver(api_key="", manual_timeout=120)


@pytest.fixture
def test_config():
    """Create a test configuration."""
    return {
        "vfs": {
            "mission": "nld"
        },
        "bot": {
            "timeout": 30
        }
    }


@pytest.fixture
def normal_user():
    """Create a normal user."""
    return User(
        id="1",
        email="user@example.com",
        password_hash="hash",
        role=UserRole.USER
    )


@pytest.fixture
def tester_user():
    """Create a tester user."""
    return User(
        id="2",
        email="tester@example.com",
        password_hash="hash",
        role=UserRole.TESTER
    )


@pytest.mark.asyncio
async def test_create_service_for_tester(tester_user, test_config, mock_captcha_solver):
    """Test that factory creates VFSApiClient for tester."""
    service = await VFSServiceFactory.create_service(
        user=tester_user,
        config=test_config,
        captcha_solver=mock_captcha_solver
    )
    
    assert isinstance(service, VFSApiClient)
    assert service.mission_code == "nld"


def test_get_service_type_for_normal_user(normal_user):
    """Test service type for normal user."""
    service_type = VFSServiceFactory.get_service_type(normal_user)
    assert service_type == "browser"


def test_get_service_type_for_tester(tester_user):
    """Test service type for tester."""
    service_type = VFSServiceFactory.get_service_type(tester_user)
    assert service_type == "api"


def test_get_service_type_for_user_with_api_setting():
    """Test service type for normal user with direct API setting."""
    user = User(
        id="3",
        email="user@example.com",
        password_hash="hash",
        role=UserRole.USER,
        settings=UserSettings(use_direct_api=True)
    )
    service_type = VFSServiceFactory.get_service_type(user)
    assert service_type == "api"


@pytest.mark.asyncio
async def test_create_service_with_custom_mission(tester_user, mock_captcha_solver):
    """Test service creation with custom mission code."""
    config = {
        "vfs": {
            "mission": "fra"
        },
        "bot": {
            "timeout": 60
        }
    }
    
    service = await VFSServiceFactory.create_service(
        user=tester_user,
        config=config,
        captcha_solver=mock_captcha_solver
    )
    
    assert isinstance(service, VFSApiClient)
    assert service.mission_code == "fra"
    assert service.timeout == 60
