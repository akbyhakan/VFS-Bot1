"""Tests for payment endpoint logic."""

import pytest
from fastapi import HTTPException, status
from unittest.mock import AsyncMock

from src.repositories import AppointmentRequestRepository, PaymentRepository


@pytest.mark.asyncio
async def test_initiate_payment_logic_returns_501():
    """Test that the payment initiation logic returns 501 when called with valid data."""
    # Import the specific function we need to test
    import sys
    import importlib.util
    
    # Load the module directly to avoid circular imports
    spec = importlib.util.spec_from_file_location(
        "payment",
        "/home/runner/work/VFS-Bot1/VFS-Bot1/web/routes/payment.py"
    )
    payment_module = importlib.util.module_from_spec(spec)
    
    # Mock the dependencies before loading
    sys.modules['web.dependencies'] = type(sys)('web.dependencies')
    sys.modules['web.models.payment'] = type(sys)('web.models.payment')
    
    # Create a mock request class
    class MockPaymentInitiateRequest:
        def __init__(self, appointment_id):
            self.appointment_id = appointment_id
    
    sys.modules['web.models.payment'].PaymentInitiateRequest = MockPaymentInitiateRequest
    
    # Now load the module
    spec.loader.exec_module(payment_module)
    
    # Test the function
    initiate_payment = payment_module.initiate_payment
    
    # Mock dependencies
    token_data = {"sub": "test_user"}
    
    # Create mock repositories
    payment_repo = AsyncMock(spec=PaymentRepository)
    payment_repo.get = AsyncMock(return_value={"id": 1, "card_holder_name": "Test User"})
    
    appt_req_repo = AsyncMock(spec=AppointmentRequestRepository)
    appt_req_repo.get_by_id = AsyncMock(return_value={"id": 1, "user_id": 1})
    
    # Create request
    request = MockPaymentInitiateRequest(appointment_id=1)
    
    # Call the endpoint and expect HTTPException with 501
    with pytest.raises(HTTPException) as exc_info:
        await initiate_payment(
            request=request,
            token_data=token_data,
            payment_repo=payment_repo,
            appt_req_repo=appt_req_repo,
        )
    
    # Verify the exception is 501 Not Implemented
    assert exc_info.value.status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert "not yet implemented" in exc_info.value.detail.lower()
