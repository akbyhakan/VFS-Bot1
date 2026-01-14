#!/usr/bin/env python3
"""
Verification script for VFS Global Dual-Mode Integration.

This script demonstrates the key features of the dual-mode system.
"""

import asyncio
from src.models.user import User, UserRole, UserSettings
from src.services.vfs_service_factory import VFSServiceFactory
from src.services.captcha_solver import CaptchaSolver
from src.core.countries import (
    validate_mission_code,
    get_route,
    get_country_info,
    get_all_mission_codes,
    SUPPORTED_COUNTRIES,
)


def test_countries():
    """Test countries configuration."""
    print("=" * 60)
    print("Testing Countries Configuration")
    print("=" * 60)
    
    # Test all countries
    all_codes = get_all_mission_codes()
    print(f"\n✓ Total supported countries: {len(all_codes)}")
    assert len(all_codes) == 21, "Should support 21 Schengen countries"
    
    # Test a few specific countries
    test_codes = ["nld", "fra", "hrv"]
    for code in test_codes:
        info = get_country_info(code)
        route = get_route(code)
        print(f"✓ {code}: {info.name_en} ({info.name_tr}) - Route: {route}")
    
    # Test validation
    try:
        validate_mission_code("invalid")
        assert False, "Should raise ValueError for invalid code"
    except ValueError as e:
        print(f"✓ Validation works: {str(e)[:50]}...")
    
    print("\n✅ Countries configuration tests passed!\n")


def test_user_model():
    """Test user model."""
    print("=" * 60)
    print("Testing User Model")
    print("=" * 60)
    
    # Test normal user
    normal_user = User(
        id="1",
        email="user@example.com",
        password_hash="hash",
        role=UserRole.USER
    )
    print(f"\n✓ Normal user created: {normal_user.email}")
    print(f"  - Role: {normal_user.role.value}")
    print(f"  - Is tester: {normal_user.is_tester}")
    print(f"  - Uses direct API: {normal_user.uses_direct_api}")
    assert not normal_user.is_tester
    assert not normal_user.uses_direct_api
    
    # Test tester user
    tester_user = User(
        id="2",
        email="tester@example.com",
        password_hash="hash",
        role=UserRole.TESTER
    )
    print(f"\n✓ Tester user created: {tester_user.email}")
    print(f"  - Role: {tester_user.role.value}")
    print(f"  - Is tester: {tester_user.is_tester}")
    print(f"  - Uses direct API: {tester_user.uses_direct_api}")
    assert tester_user.is_tester
    assert tester_user.uses_direct_api
    
    # Test user with API setting
    user_with_api = User(
        id="3",
        email="api_user@example.com",
        password_hash="hash",
        role=UserRole.USER,
        settings=UserSettings(use_direct_api=True)
    )
    print(f"\n✓ User with API setting: {user_with_api.email}")
    print(f"  - Role: {user_with_api.role.value}")
    print(f"  - Is tester: {user_with_api.is_tester}")
    print(f"  - Uses direct API: {user_with_api.uses_direct_api}")
    assert not user_with_api.is_tester
    assert user_with_api.uses_direct_api
    
    print("\n✅ User model tests passed!\n")


async def test_service_factory():
    """Test service factory."""
    print("=" * 60)
    print("Testing Service Factory")
    print("=" * 60)
    
    config = {
        "vfs": {"mission": "nld"},
        "bot": {"timeout": 30}
    }
    
    captcha_solver = CaptchaSolver(api_key="", manual_timeout=120)
    
    # Test service type detection
    normal_user = User(
        id="1",
        email="user@example.com",
        password_hash="hash",
        role=UserRole.USER
    )
    
    tester_user = User(
        id="2",
        email="tester@example.com",
        password_hash="hash",
        role=UserRole.TESTER
    )
    
    normal_type = VFSServiceFactory.get_service_type(normal_user)
    tester_type = VFSServiceFactory.get_service_type(tester_user)
    
    print(f"\n✓ Normal user service type: {normal_type}")
    print(f"✓ Tester user service type: {tester_type}")
    
    assert normal_type == "browser"
    assert tester_type == "api"
    
    # Test service creation for tester
    tester_service = await VFSServiceFactory.create_service(
        user=tester_user,
        config=config,
        captcha_solver=captcha_solver
    )
    
    print(f"\n✓ Created service for tester: {type(tester_service).__name__}")
    print(f"  - Mission code: {tester_service.mission_code}")
    print(f"  - Route: {tester_service.route}")
    
    assert tester_service.mission_code == "nld"
    assert hasattr(tester_service, 'IS_DIRECT_API')
    assert tester_service.IS_DIRECT_API is True
    
    print("\n✅ Service factory tests passed!\n")


def main():
    """Run all verification tests."""
    print("\n" + "=" * 60)
    print("VFS GLOBAL DUAL-MODE INTEGRATION - VERIFICATION")
    print("=" * 60 + "\n")
    
    # Run synchronous tests
    test_countries()
    test_user_model()
    
    # Run async tests
    asyncio.run(test_service_factory())
    
    print("=" * 60)
    print("ALL VERIFICATION TESTS PASSED! ✅")
    print("=" * 60 + "\n")
    
    print("Summary:")
    print("--------")
    print("✓ Countries: 21 Schengen countries configured")
    print("✓ User Model: Role-based access working")
    print("✓ Service Factory: Correct service selection")
    print("✓ API Client: Test user integration ready")
    print("\nThe dual-mode system is ready to use!")


if __name__ == "__main__":
    main()
