"""Tests for custom exceptions."""

import pytest

from src.core.exceptions import (
    AuthenticationError,
    BannedError,
    BatchOperationError,
    BookingError,
    CaptchaError,
    CaptchaRequiredError,
    CaptchaTimeoutError,
    CircuitBreakerOpenError,
    ConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    DatabaseNotConnectedError,
    DatabasePoolTimeoutError,
    InsufficientPermissionsError,
    InvalidCredentialsError,
    LoginError,
    MissingEnvironmentVariableError,
    NetworkError,
    OTPError,
    OTPInvalidError,
    OTPTimeoutError,
    PaymentCardNotFoundError,
    PaymentError,
    PaymentFailedError,
    PaymentProcessingError,
    RateLimitError,
    RecordNotFoundError,
    SelectorNotFoundError,
    SessionBindingError,
    SessionError,
    SessionExpiredError,
    ShutdownTimeoutError,
    SlotCheckError,
    TokenExpiredError,
    ValidationError,
    VFSApiError,
    VFSAuthenticationError,
    VFSBotError,
    VFSRateLimitError,
    VFSSessionExpiredError,
    VFSSlotNotFoundError,
)


def test_vfsbot_error():
    """Test VFSBotError base exception."""
    error = VFSBotError("Test error")
    assert error.message == "Test error"
    assert error.recoverable is True
    assert str(error) == "Test error"


def test_vfsbot_error_not_recoverable():
    """Test VFSBotError with recoverable=False."""
    error = VFSBotError("Fatal error", recoverable=False)
    assert error.message == "Fatal error"
    assert error.recoverable is False


def test_login_error_default():
    """Test LoginError with default message."""
    error = LoginError()
    assert error.message == "Login failed"
    assert error.recoverable is False


def test_login_error_custom():
    """Test LoginError with custom message."""
    error = LoginError("Invalid credentials")
    assert error.message == "Invalid credentials"


def test_login_error_not_recoverable():
    """Test LoginError with recoverable=False."""
    error = LoginError(recoverable=False)
    assert error.recoverable is False


def test_captcha_error_default():
    """Test CaptchaError with default message."""
    error = CaptchaError()
    assert error.message == "Captcha verification failed"
    assert error.recoverable is True


def test_captcha_error_custom():
    """Test CaptchaError with custom message."""
    error = CaptchaError("Captcha timeout")
    assert error.message == "Captcha timeout"


def test_slot_check_error_default():
    """Test SlotCheckError with default message."""
    error = SlotCheckError()
    assert error.message == "Slot check failed"
    assert error.recoverable is True


def test_slot_check_error_custom():
    """Test SlotCheckError with custom message."""
    error = SlotCheckError("No slots available")
    assert error.message == "No slots available"


def test_booking_error_default():
    """Test BookingError with default message."""
    error = BookingError()
    assert error.message == "Booking failed"
    assert error.recoverable is False  # BookingError defaults to False


def test_booking_error_custom():
    """Test BookingError with custom message."""
    error = BookingError("Payment declined")
    assert error.message == "Payment declined"


def test_network_error_default():
    """Test NetworkError with default message."""
    error = NetworkError()
    assert error.message == "Network error occurred"
    assert error.recoverable is True


def test_network_error_custom():
    """Test NetworkError with custom message."""
    error = NetworkError("Connection timeout")
    assert error.message == "Connection timeout"


def test_selector_not_found_error():
    """Test SelectorNotFoundError."""
    error = SelectorNotFoundError("login_button")
    assert error.selector_name == "login_button"
    assert error.tried_selectors == []
    assert "Selector 'login_button' not found" in error.message
    assert error.recoverable is False


def test_selector_not_found_error_with_tried_selectors():
    """Test SelectorNotFoundError with tried selectors."""
    tried = ["#login", ".login-btn", "button[type='submit']"]
    error = SelectorNotFoundError("login_button", tried_selectors=tried)

    assert error.selector_name == "login_button"
    assert error.tried_selectors == tried
    assert "Tried:" in error.message
    assert "#login" in error.message


def test_rate_limit_error_default():
    """Test RateLimitError with default message."""
    error = RateLimitError()
    assert error.message == "Rate limit exceeded"
    assert error.retry_after is None
    assert error.recoverable is True


def test_rate_limit_error_with_wait_time():
    """Test RateLimitError with wait time."""
    error = RateLimitError(retry_after=60)
    assert error.retry_after == 60
    assert "wait 60 seconds" in error.message


def test_configuration_error_default():
    """Test ConfigurationError with default message."""
    error = ConfigurationError()
    assert error.message == "Configuration error"
    assert error.recoverable is False  # ConfigurationError defaults to False


def test_configuration_error_custom():
    """Test ConfigurationError with custom message."""
    error = ConfigurationError("Invalid API key")
    assert error.message == "Invalid API key"


def test_authentication_error_default():
    """Test AuthenticationError with default message."""
    error = AuthenticationError()
    assert error.message == "Authentication failed"
    assert error.recoverable is False  # AuthenticationError defaults to False


def test_authentication_error_custom():
    """Test AuthenticationError with custom message."""
    error = AuthenticationError("Invalid token")
    assert error.message == "Invalid token"


def test_exceptions_are_raisable():
    """Test that exceptions can be raised and caught."""
    with pytest.raises(VFSBotError) as exc_info:
        raise VFSBotError("Test")
    assert exc_info.value.message == "Test"

    with pytest.raises(LoginError):
        raise LoginError()

    with pytest.raises(CaptchaError):
        raise CaptchaError()

    with pytest.raises(CaptchaTimeoutError):
        raise CaptchaTimeoutError()

    with pytest.raises(SlotCheckError):
        raise SlotCheckError()

    with pytest.raises(BookingError):
        raise BookingError()

    with pytest.raises(SessionError):
        raise SessionError()

    with pytest.raises(SessionExpiredError):
        raise SessionExpiredError()

    with pytest.raises(SessionBindingError):
        raise SessionBindingError()

    with pytest.raises(NetworkError):
        raise NetworkError()

    with pytest.raises(SelectorNotFoundError):
        raise SelectorNotFoundError("test")

    with pytest.raises(RateLimitError):
        raise RateLimitError()

    with pytest.raises(CircuitBreakerOpenError):
        raise CircuitBreakerOpenError()

    with pytest.raises(ConfigurationError):
        raise ConfigurationError()

    with pytest.raises(MissingEnvironmentVariableError):
        raise MissingEnvironmentVariableError("TEST_VAR")

    with pytest.raises(AuthenticationError):
        raise AuthenticationError()

    with pytest.raises(InvalidCredentialsError):
        raise InvalidCredentialsError()

    with pytest.raises(TokenExpiredError):
        raise TokenExpiredError()

    with pytest.raises(InsufficientPermissionsError):
        raise InsufficientPermissionsError("admin")

    with pytest.raises(VFSApiError):
        raise VFSApiError()

    with pytest.raises(VFSAuthenticationError):
        raise VFSAuthenticationError()

    with pytest.raises(VFSRateLimitError):
        raise VFSRateLimitError()

    with pytest.raises(VFSSlotNotFoundError):
        raise VFSSlotNotFoundError()

    with pytest.raises(VFSSessionExpiredError):
        raise VFSSessionExpiredError()

    with pytest.raises(CaptchaRequiredError):
        raise CaptchaRequiredError()

    with pytest.raises(BannedError):
        raise BannedError()

    with pytest.raises(ValidationError):
        raise ValidationError()

    with pytest.raises(DatabaseError):
        raise DatabaseError()

    with pytest.raises(DatabaseConnectionError):
        raise DatabaseConnectionError()

    with pytest.raises(DatabaseNotConnectedError):
        raise DatabaseNotConnectedError()

    with pytest.raises(DatabasePoolTimeoutError):
        raise DatabasePoolTimeoutError(timeout=5.0, pool_size=10)

    with pytest.raises(RecordNotFoundError):
        raise RecordNotFoundError("User", 123)

    with pytest.raises(PaymentError):
        raise PaymentError()

    with pytest.raises(PaymentCardNotFoundError):
        raise PaymentCardNotFoundError()

    with pytest.raises(PaymentProcessingError):
        raise PaymentProcessingError()

    with pytest.raises(PaymentFailedError):
        raise PaymentFailedError()

    with pytest.raises(OTPError):
        raise OTPError()

    with pytest.raises(OTPTimeoutError):
        raise OTPTimeoutError(30)

    with pytest.raises(OTPInvalidError):
        raise OTPInvalidError()

    with pytest.raises(ShutdownTimeoutError):
        raise ShutdownTimeoutError()

    with pytest.raises(BatchOperationError):
        raise BatchOperationError()


def test_exceptions_inherit_from_vfsbot_error():
    """Test that all custom exceptions inherit from VFSBotError."""
    assert issubclass(LoginError, VFSBotError)
    assert issubclass(CaptchaError, VFSBotError)
    assert issubclass(CaptchaTimeoutError, CaptchaError)
    assert issubclass(SlotCheckError, VFSBotError)
    assert issubclass(BookingError, VFSBotError)
    assert issubclass(SessionError, VFSBotError)
    assert issubclass(SessionExpiredError, SessionError)
    assert issubclass(SessionBindingError, SessionError)
    assert issubclass(NetworkError, VFSBotError)
    assert issubclass(SelectorNotFoundError, VFSBotError)
    assert issubclass(RateLimitError, VFSBotError)
    assert issubclass(CircuitBreakerOpenError, VFSBotError)
    assert issubclass(ConfigurationError, VFSBotError)
    assert issubclass(MissingEnvironmentVariableError, ConfigurationError)
    assert issubclass(AuthenticationError, VFSBotError)
    assert issubclass(InvalidCredentialsError, AuthenticationError)
    assert issubclass(TokenExpiredError, AuthenticationError)
    assert issubclass(InsufficientPermissionsError, AuthenticationError)
    assert issubclass(VFSApiError, VFSBotError)
    assert issubclass(VFSAuthenticationError, VFSApiError)
    assert issubclass(VFSRateLimitError, VFSApiError)
    assert issubclass(VFSSlotNotFoundError, VFSApiError)
    assert issubclass(VFSSessionExpiredError, VFSApiError)
    assert issubclass(CaptchaRequiredError, VFSApiError)
    assert issubclass(BannedError, VFSApiError)
    assert issubclass(ValidationError, VFSBotError)
    assert issubclass(DatabaseError, VFSBotError)
    assert issubclass(DatabaseConnectionError, DatabaseError)
    assert issubclass(DatabaseNotConnectedError, DatabaseError)
    assert issubclass(DatabasePoolTimeoutError, DatabaseError)
    assert issubclass(RecordNotFoundError, DatabaseError)
    assert issubclass(PaymentError, VFSBotError)
    assert issubclass(PaymentCardNotFoundError, PaymentError)
    assert issubclass(PaymentProcessingError, PaymentError)
    assert issubclass(PaymentFailedError, PaymentProcessingError)
    assert issubclass(OTPError, VFSBotError)
    assert issubclass(OTPTimeoutError, OTPError)
    assert issubclass(OTPInvalidError, OTPError)
    assert issubclass(ShutdownTimeoutError, VFSBotError)
    assert issubclass(BatchOperationError, DatabaseError)


def test_error_type_uri_property():
    """Test that error_type_uri property works correctly with re module at top."""
    error = RateLimitError()
    assert error.error_type_uri == "urn:vfsbot:error:rate-limit"
    
    login_error = LoginError()
    assert login_error.error_type_uri == "urn:vfsbot:error:login"
    
    booking_error = BookingError()
    assert booking_error.error_type_uri == "urn:vfsbot:error:booking"


def test_title_property():
    """Test that title property works correctly with re module at top."""
    error = RateLimitError()
    assert error.title == "Rate Limit Error"
    
    login_error = LoginError()
    assert login_error.title == "Login Error"
    
    booking_error = BookingError()
    assert booking_error.title == "Booking Error"


def test_http_status_codes():
    """Test that exceptions return correct HTTP status codes."""
    # ValidationError should return 400
    validation_error = ValidationError("Test validation")
    assert validation_error._get_http_status() == 400
    
    # AuthenticationError should return 401
    auth_error = AuthenticationError()
    assert auth_error._get_http_status() == 401
    
    # RateLimitError should return 429
    rate_limit_error = RateLimitError()
    assert rate_limit_error._get_http_status() == 429
    
    # DatabaseError should return 500
    db_error = DatabaseError()
    assert db_error._get_http_status() == 500


def test_error_type_uri_for_new_exceptions():
    """Test error_type_uri property for new exceptions."""
    assert SessionError().error_type_uri == "urn:vfsbot:error:session"
    assert SessionExpiredError().error_type_uri == "urn:vfsbot:error:session-expired"
    assert SessionBindingError().error_type_uri == "urn:vfsbot:error:session-binding"
    assert CaptchaTimeoutError().error_type_uri == "urn:vfsbot:error:captcha-timeout"
    assert CircuitBreakerOpenError().error_type_uri == "urn:vfsbot:error:circuit-breaker-open"
    assert MissingEnvironmentVariableError("TEST").error_type_uri == "urn:vfsbot:error:missing-environment-variable"
    assert InvalidCredentialsError().error_type_uri == "urn:vfsbot:error:invalid-credentials"
    assert TokenExpiredError().error_type_uri == "urn:vfsbot:error:token-expired"
    assert InsufficientPermissionsError("admin").error_type_uri == "urn:vfsbot:error:insufficient-permissions"
    assert VFSApiError().error_type_uri == "urn:vfsbot:error:v-f-s-api"
    assert VFSAuthenticationError().error_type_uri == "urn:vfsbot:error:v-f-s-authentication"
    assert VFSRateLimitError().error_type_uri == "urn:vfsbot:error:v-f-s-rate-limit"
    assert VFSSlotNotFoundError().error_type_uri == "urn:vfsbot:error:v-f-s-slot-not-found"
    assert VFSSessionExpiredError().error_type_uri == "urn:vfsbot:error:v-f-s-session-expired"
    assert CaptchaRequiredError().error_type_uri == "urn:vfsbot:error:captcha-required"
    assert BannedError().error_type_uri == "urn:vfsbot:error:banned"
    assert ValidationError().error_type_uri == "urn:vfsbot:error:validation"
    assert DatabaseError().error_type_uri == "urn:vfsbot:error:database"
    assert DatabaseConnectionError().error_type_uri == "urn:vfsbot:error:database-connection"
    assert DatabaseNotConnectedError().error_type_uri == "urn:vfsbot:error:database-not-connected"
    assert DatabasePoolTimeoutError(5.0, 10).error_type_uri == "urn:vfsbot:error:database-pool-timeout"
    assert RecordNotFoundError("User", 1).error_type_uri == "urn:vfsbot:error:record-not-found"
    assert PaymentError().error_type_uri == "urn:vfsbot:error:payment"
    assert PaymentCardNotFoundError().error_type_uri == "urn:vfsbot:error:payment-card-not-found"
    assert PaymentProcessingError().error_type_uri == "urn:vfsbot:error:payment-processing"
    assert PaymentFailedError().error_type_uri == "urn:vfsbot:error:payment-failed"
    assert OTPError().error_type_uri == "urn:vfsbot:error:o-t-p"
    assert OTPTimeoutError(30).error_type_uri == "urn:vfsbot:error:o-t-p-timeout"
    assert OTPInvalidError().error_type_uri == "urn:vfsbot:error:o-t-p-invalid"
    assert ShutdownTimeoutError().error_type_uri == "urn:vfsbot:error:shutdown-timeout"
    assert BatchOperationError().error_type_uri == "urn:vfsbot:error:batch-operation"


def test_title_for_new_exceptions():
    """Test title property for new exceptions."""
    assert SessionError().title == "Session Error"
    assert SessionExpiredError().title == "Session Expired Error"
    assert SessionBindingError().title == "Session Binding Error"
    assert CaptchaTimeoutError().title == "Captcha Timeout Error"
    assert CircuitBreakerOpenError().title == "Circuit Breaker Open Error"
    assert MissingEnvironmentVariableError("TEST").title == "Missing Environment Variable Error"
    assert InvalidCredentialsError().title == "Invalid Credentials Error"
    assert TokenExpiredError().title == "Token Expired Error"
    assert InsufficientPermissionsError("admin").title == "Insufficient Permissions Error"
    assert VFSApiError().title == "V F S Api Error"
    assert VFSAuthenticationError().title == "V F S Authentication Error"
    assert VFSRateLimitError().title == "V F S Rate Limit Error"
    assert VFSSlotNotFoundError().title == "V F S Slot Not Found Error"
    assert VFSSessionExpiredError().title == "V F S Session Expired Error"
    assert CaptchaRequiredError().title == "Captcha Required Error"
    assert BannedError().title == "Banned Error"
    assert ValidationError().title == "Validation Error"
    assert DatabaseError().title == "Database Error"
    assert DatabaseConnectionError().title == "Database Connection Error"
    assert DatabaseNotConnectedError().title == "Database Not Connected Error"
    assert DatabasePoolTimeoutError(5.0, 10).title == "Database Pool Timeout Error"
    assert RecordNotFoundError("User", 1).title == "Record Not Found Error"
    assert PaymentError().title == "Payment Error"
    assert PaymentCardNotFoundError().title == "Payment Card Not Found Error"
    assert PaymentProcessingError().title == "Payment Processing Error"
    assert PaymentFailedError().title == "Payment Failed Error"
    assert OTPError().title == "O T P Error"
    assert OTPTimeoutError(30).title == "O T P Timeout Error"
    assert OTPInvalidError().title == "O T P Invalid Error"
    assert ShutdownTimeoutError().title == "Shutdown Timeout Error"
    assert BatchOperationError().title == "Batch Operation Error"


def test_to_dict_for_exceptions():
    """Test that to_dict method works for all exceptions."""
    error = ValidationError("Invalid field", field="email")
    error_dict = error.to_dict()
    assert error_dict["type"] == "urn:vfsbot:error:validation"
    assert error_dict["title"] == "Validation Error"
    assert error_dict["status"] == 400
    assert "Invalid field" in error_dict["detail"]
    assert error_dict["recoverable"] is False
    assert "timestamp" in error_dict
    
    # Test DatabaseError
    db_error = DatabaseError("Connection lost")
    db_dict = db_error.to_dict()
    assert db_dict["type"] == "urn:vfsbot:error:database"
    assert db_dict["status"] == 500
    assert db_dict["detail"] == "Connection lost"
    
    # Test RateLimitError
    rate_error = RateLimitError(retry_after=60)
    rate_dict = rate_error.to_dict()
    assert rate_dict["status"] == 429
    assert rate_dict["retry_after"] == 60


def test_new_exception_specific_behaviors():
    """Test specific behaviors of new exceptions."""
    # Test MissingEnvironmentVariableError
    missing_env = MissingEnvironmentVariableError("API_KEY")
    assert "API_KEY" in missing_env.message
    assert missing_env.details["variable"] == "API_KEY"
    assert missing_env.recoverable is False
    
    # Test DatabasePoolTimeoutError
    pool_error = DatabasePoolTimeoutError(timeout=5.0, pool_size=10)
    assert pool_error.details["timeout"] == 5.0
    assert pool_error.details["pool_size"] == 10
    assert "5.0" in pool_error.message
    assert "10" in pool_error.message
    
    # Test RecordNotFoundError
    not_found = RecordNotFoundError("User", 123)
    assert not_found.details["resource_type"] == "User"
    assert not_found.details["resource_id"] == 123
    assert "User" in not_found.message
    assert "123" in not_found.message
    
    # Test InsufficientPermissionsError
    permissions_error = InsufficientPermissionsError("admin")
    assert permissions_error.details["required_permission"] == "admin"
    assert "admin" in permissions_error.message
    
    # Test OTPTimeoutError
    otp_timeout = OTPTimeoutError(30)
    assert otp_timeout.details["timeout_seconds"] == 30
    assert "30" in otp_timeout.message
    
    # Test BatchOperationError
    batch_error = BatchOperationError(
        operation="bulk_insert",
        failed_count=5,
        total_count=100
    )
    assert batch_error.details["operation"] == "bulk_insert"
    assert batch_error.details["failed_count"] == 5
    assert batch_error.details["total_count"] == 100
    assert batch_error.details["success_count"] == 95
