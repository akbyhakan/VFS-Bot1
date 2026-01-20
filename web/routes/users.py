"""User management routes for VFS-Bot web application."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from src.models.database import Database
from src.core.exceptions import ValidationError
from web.dependencies import (
    verify_jwt_token,
    UserModel,
    UserCreateRequest,
    UserUpdateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserModel])
async def get_users(token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Get all users from database - requires authentication.

    Args:
        token_data: Verified token data

    Returns:
        List of users with their personal details
    """
    db = Database()
    try:
        await db.connect()
        users_data = await db.get_all_users_with_details()

        # Convert database records to UserModel format
        users = []
        for user in users_data:
            users.append(
                UserModel(
                    id=user["id"],
                    email=user["email"],
                    phone=user.get("phone") or "",
                    first_name=user.get("first_name") or "",
                    last_name=user.get("last_name") or "",
                    center_name=user["center_name"],
                    visa_category=user["visa_category"],
                    visa_subcategory=user["visa_subcategory"],
                    is_active=bool(user["is_active"]),
                    created_at=user["created_at"],
                    updated_at=user["updated_at"],
                )
            )

        return users
    finally:
        await db.close()


@router.post("", response_model=UserModel)
async def create_user(
    user: UserCreateRequest, token_data: Dict[str, Any] = Depends(verify_jwt_token)
):
    """
    Create a new user in database - requires authentication.

    Args:
        user: User data
        token_data: Verified token data

    Returns:
        Created user

    Raises:
        HTTPException: If user creation fails
    """
    db = Database()
    try:
        await db.connect()

        # Create user record
        user_id = await db.add_user(
            email=user.email,
            password=user.password,
            centre=user.center_name,
            category=user.visa_category,
            subcategory=user.visa_subcategory,
        )

        # Create personal details record
        await db.add_personal_details(
            user_id=user_id,
            details={
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "mobile_number": user.phone,
                "passport_number": "",  # Required field, empty for now
            },
        )

        # Set user as active/inactive
        if not user.is_active:
            await db.update_user(user_id, active=False)

        # Get the created user with details
        users = await db.get_all_users_with_details()
        created_user = next((u for u in users if u["id"] == user_id), None)

        if not created_user:
            raise HTTPException(status_code=500, detail="Failed to retrieve created user")

        logger.info(f"User created: {user.email} by {token_data.get('sub', 'unknown')}")

        return UserModel(
            id=created_user["id"],
            email=created_user["email"],
            phone=created_user.get("phone") or "",
            first_name=created_user.get("first_name") or "",
            last_name=created_user.get("last_name") or "",
            center_name=created_user["center_name"],
            visa_category=created_user["visa_category"],
            visa_subcategory=created_user["visa_subcategory"],
            is_active=bool(created_user["is_active"]),
            created_at=created_user["created_at"],
            updated_at=created_user["updated_at"],
        )

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create user")
    finally:
        await db.close()


@router.put("/{user_id}", response_model=UserModel)
async def update_user(
    user_id: int,
    user_update: UserUpdateRequest,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
):
    """
    Update a user in database - requires authentication.

    Args:
        user_id: User ID
        user_update: Updated user data
        token_data: Verified token data

    Returns:
        Updated user

    Raises:
        HTTPException: If user not found or update fails
    """
    db = Database()
    try:
        await db.connect()

        # Update user table fields (including password if provided)
        user_updated = await db.update_user(
            user_id=user_id,
            email=user_update.email,
            password=user_update.password,
            centre=user_update.center_name,
            category=user_update.visa_category,
            subcategory=user_update.visa_subcategory,
            active=user_update.is_active,
        )

        if not user_updated:
            raise HTTPException(status_code=404, detail="User not found")

        # Update personal details if provided
        if any([user_update.first_name, user_update.last_name, user_update.phone]):
            await db.update_personal_details(
                user_id=user_id,
                first_name=user_update.first_name,
                last_name=user_update.last_name,
                mobile_number=user_update.phone,
            )

        # Get updated user
        users = await db.get_all_users_with_details()
        updated_user = next((u for u in users if u["id"] == user_id), None)

        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found after update")

        logger.info(f"User updated: {updated_user['email']} by {token_data.get('sub', 'unknown')}")

        return UserModel(
            id=updated_user["id"],
            email=updated_user["email"],
            phone=updated_user.get("phone") or "",
            first_name=updated_user.get("first_name") or "",
            last_name=updated_user.get("last_name") or "",
            center_name=updated_user["center_name"],
            visa_category=updated_user["visa_category"],
            visa_subcategory=updated_user["visa_subcategory"],
            is_active=bool(updated_user["is_active"]),
            created_at=updated_user["created_at"],
            updated_at=updated_user["updated_at"],
        )

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update user")
    finally:
        await db.close()


@router.delete("/{user_id}")
async def delete_user(user_id: int, token_data: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Delete a user from database - requires authentication.

    Args:
        user_id: User ID
        token_data: Verified token data

    Returns:
        Success message

    Raises:
        HTTPException: If user not found
    """
    db = Database()
    try:
        await db.connect()

        # Get user email before deletion for logging
        users = await db.get_all_users_with_details()
        user = next((u for u in users if u["id"] == user_id), None)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Delete user (cascades to personal_details due to FOREIGN KEY)
        deleted = await db.delete_user(user_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"User deleted: {user['email']} by {token_data.get('sub', 'unknown')}")
        return {"message": "User deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete user")
    finally:
        await db.close()


@router.patch("/{user_id}", response_model=UserModel)
async def toggle_user_status(
    user_id: int,
    status_update: Dict[str, bool],
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
):
    """
    Toggle user active status - requires authentication.

    Args:
        user_id: User ID
        status_update: Status update data (is_active)
        token_data: Verified token data

    Returns:
        Updated user
    """
    db = Database()
    try:
        await db.connect()

        if "is_active" not in status_update:
            raise HTTPException(status_code=400, detail="is_active field required")

        user_updated = await db.update_user(
            user_id=user_id,
            active=status_update["is_active"],
        )

        if not user_updated:
            raise HTTPException(status_code=404, detail="User not found")

        # Efficiently fetch just the updated user with details
        async with db.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT
                        u.id, u.email, u.centre as center_name,
                        u.category as visa_category, u.subcategory as visa_subcategory,
                        u.active as is_active, u.created_at, u.updated_at,
                        p.first_name, p.last_name, p.mobile_number as phone
                    FROM users u
                    LEFT JOIN personal_details p ON u.id = p.user_id
                    WHERE u.id = ?
                """,
                    (user_id,),
                )
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="User not found after update")
                updated_user = dict(row)

        logger.info(
            f"User status toggled: {updated_user['email']} -> {status_update['is_active']} "
            f"by {token_data.get('sub', 'unknown')}"
        )

        return UserModel(
            id=updated_user["id"],
            email=updated_user["email"],
            phone=updated_user.get("phone") or "",
            first_name=updated_user.get("first_name") or "",
            last_name=updated_user.get("last_name") or "",
            center_name=updated_user["center_name"],
            visa_category=updated_user["visa_category"],
            visa_subcategory=updated_user["visa_subcategory"],
            is_active=bool(updated_user["is_active"]),
            created_at=updated_user["created_at"],
            updated_at=updated_user["updated_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling user status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to toggle user status")
    finally:
        await db.close()
