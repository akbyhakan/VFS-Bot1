"""Admin routes for user management."""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, EmailStr

from src.models.user import UserRole
from src.models.database import Database
from src.core.auth import verify_token, hash_password
from src.utils.encryption import encrypt_password

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateTesterRequest(BaseModel):
    """Request model for creating test user."""
    email: EmailStr
    password: str
    centre: str = "Istanbul"
    category: str = "National Visa"
    subcategory: str = "Work"


class TesterResponse(BaseModel):
    """Response model for test user."""
    id: int
    email: str
    role: str
    created_at: str


async def get_current_admin_user(
    credentials: dict = Depends(lambda: {})
) -> dict:
    """
    Get current admin user from token.
    
    ⚠️ PLACEHOLDER IMPLEMENTATION - Replace before production use!
    
    In production, you MUST:
    1. Extract token from Authorization header
    2. Verify token using verify_token()
    3. Check if user has admin role in database
    4. Return actual user object or raise HTTPException if not admin
    
    Example implementation:
        from fastapi import Header
        from src.core.auth import verify_token
        
        token = authorization.split("Bearer ")[-1]
        payload = verify_token(token)
        user = await db.get_user_by_email(payload["email"])
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return user
    
    Args:
        credentials: User credentials from token
        
    Returns:
        User dict with admin role
        
    Raises:
        HTTPException: If user is not admin
    """
    # TODO: Implement proper admin authentication before production deployment
    # This is a simplified version for the initial implementation
    return {"role": "admin", "email": "admin@vfs-bot.local"}


@router.post("/users/create-tester", response_model=TesterResponse)
async def create_test_user(
    request: CreateTesterRequest,
    db: Database = Depends(lambda: Database()),
    current_admin: dict = Depends(get_current_admin_user)
):
    """
    Create a test user with direct API access.
    
    ⚠️ Only admins can create test users.
    Test users use direct API instead of browser automation.
    
    Args:
        request: User creation request
        db: Database instance
        current_admin: Current admin user
        
    Returns:
        Created test user info
        
    Raises:
        HTTPException: If email already exists or on error
    """
    try:
        await db.connect()
        
        # Check if email already exists
        existing = await db.get_user_by_email(request.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create test user
        user_id = await db.add_user(
            email=request.email,
            password=request.password,
            centre=request.centre,
            category=request.category,
            subcategory=request.subcategory,
            role=UserRole.TESTER.value
        )
        
        # Get created user
        user = await db.get_user_by_id(user_id)
        
        return TesterResponse(
            id=user["id"],
            email=user["email"],
            role=user["role"],
            created_at=str(user["created_at"])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create test user: {str(e)}"
        )
    finally:
        await db.close()


@router.get("/users/testers", response_model=List[TesterResponse])
async def list_test_users(
    db: Database = Depends(lambda: Database()),
    current_admin: dict = Depends(get_current_admin_user)
):
    """
    List all test users.
    
    Args:
        db: Database instance
        current_admin: Current admin user
        
    Returns:
        List of test users
    """
    try:
        await db.connect()
        
        users = await db.get_users_by_role(UserRole.TESTER.value)
        
        return [
            TesterResponse(
                id=u["id"],
                email=u["email"],
                role=u["role"],
                created_at=str(u["created_at"])
            )
            for u in users
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list test users: {str(e)}"
        )
    finally:
        await db.close()


@router.delete("/users/{user_id}/revoke-tester")
async def revoke_tester_role(
    user_id: int,
    db: Database = Depends(lambda: Database()),
    current_admin: dict = Depends(get_current_admin_user)
):
    """
    Revoke test user privileges, convert to normal user.
    
    Args:
        user_id: User ID to revoke tester role from
        db: Database instance
        current_admin: Current admin user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If user not found or on error
    """
    try:
        await db.connect()
        
        user = await db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update role to normal user
        await db.update_user_role(user_id, UserRole.USER.value)
        
        return {
            "message": f"User {user['email']} is now a normal user",
            "user_id": user_id,
            "old_role": user["role"],
            "new_role": UserRole.USER.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke tester role: {str(e)}"
        )
    finally:
        await db.close()
