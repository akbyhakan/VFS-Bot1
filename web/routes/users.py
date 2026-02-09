"""User management routes for VFS-Bot web application."""

import csv
import io
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.core.exceptions import ValidationError
from src.repositories import UserRepository
from web.dependencies import UserCreateRequest, UserModel, UserUpdateRequest, get_user_repository, verify_jwt_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserModel])
async def get_users(
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Get all users from database - requires authentication.

    Args:
        token_data: Verified token data
        user_repo: UserRepository instance

    Returns:
        List of users with their personal details
    """
    users_data = await user_repo.get_all_with_details()

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


@router.post("", response_model=UserModel)
async def create_user(
    user: UserCreateRequest,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Create a new user in database - requires authentication.

    Args:
        user: User data
        token_data: Verified token data
        user_repo: UserRepository instance

    Returns:
        Created user

    Raises:
        HTTPException: If user creation fails
    """
    try:
        # Build user data dictionary
        user_data = {
            "email": user.email,
            "password": user.password,
            "centre": user.center_name,
            "category": user.visa_category,
            "subcategory": user.visa_subcategory,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "is_active": user.is_active,
        }

        # Create user with repository
        user_id = await user_repo.create(user_data)

        # Get the created user with details
        created_user = await user_repo.get_by_id_with_details(user_id)

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


@router.put("/{user_id}", response_model=UserModel)
async def update_user(
    user_id: int,
    user_update: UserUpdateRequest,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Update a user in database - requires authentication.

    Args:
        user_id: User ID
        user_update: Updated user data
        token_data: Verified token data
        user_repo: UserRepository instance

    Returns:
        Updated user

    Raises:
        HTTPException: If user not found or update fails
    """
    try:
        # Build update data dictionary
        update_data = {
            "email": user_update.email,
            "password": user_update.password,
            "centre": user_update.center_name,
            "category": user_update.visa_category,
            "subcategory": user_update.visa_subcategory,
            "is_active": user_update.is_active,
        }

        # Update user
        user_updated = await user_repo.update(user_id, update_data)

        if not user_updated:
            raise HTTPException(status_code=404, detail="User not found")

        # Update personal details if provided
        if any([user_update.first_name, user_update.last_name, user_update.phone]):
            await user_repo.update_personal_details(
                user_id=user_id,
                first_name=user_update.first_name,
                last_name=user_update.last_name,
                mobile_number=user_update.phone,
            )

        # Get updated user
        updated_user = await user_repo.get_by_id_with_details(user_id)

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


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Delete a user from database - requires authentication.

    Args:
        user_id: User ID
        token_data: Verified token data
        user_repo: UserRepository instance

    Returns:
        Success message

    Raises:
        HTTPException: If user not found
    """
    try:
        # Get user email before deletion for logging
        user = await user_repo.get_by_id_with_details(user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Delete user (cascades to personal_details due to FOREIGN KEY)
        deleted = await user_repo.delete(user_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"User deleted: {user['email']} by {token_data.get('sub', 'unknown')}")
        return {"message": "User deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete user")


@router.patch("/{user_id}", response_model=UserModel)
async def toggle_user_status(
    user_id: int,
    status_update: Dict[str, bool],
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Toggle user active status - requires authentication.

    Args:
        user_id: User ID
        status_update: Status update data (is_active)
        token_data: Verified token data
        user_repo: UserRepository instance

    Returns:
        Updated user
    """
    try:
        if "is_active" not in status_update:
            raise HTTPException(status_code=400, detail="is_active field required")

        update_data = {"is_active": status_update["is_active"]}
        user_updated = await user_repo.update(user_id, update_data)

        if not user_updated:
            raise HTTPException(status_code=404, detail="User not found")

        # Get updated user with details
        updated_user = await user_repo.get_by_id_with_details(user_id)
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found after update")

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


@router.post("/import")
async def import_users_csv(
    file: UploadFile = File(...),
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Import users from CSV file - requires authentication.

    CSV Format:
    email,password,first_name,last_name,phone,centre,visa_category,visa_subcategory

    Args:
        file: CSV file to import
        token_data: Verified token data
        user_repo: UserRepository instance

    Returns:
        Import results with success/failure counts and error messages

    Raises:
        HTTPException: If file is not CSV or import fails
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Sadece CSV dosyası kabul edilir")

    try:
        # Read file content
        content = await file.read()

        # Handle BOM (Byte Order Mark) for UTF-8
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Dosya kodlaması desteklenmiyor. UTF-8 veya Latin-1 kullanın.",
                )

        # Parse CSV
        reader = csv.DictReader(io.StringIO(text))

        # Validate headers
        expected_headers = {
            "email",
            "password",
            "first_name",
            "last_name",
            "phone",
            "centre",
            "visa_category",
            "visa_subcategory",
        }
        if reader.fieldnames is None:
            raise HTTPException(status_code=400, detail="CSV dosyası boş veya geçersiz")

        actual_headers = set(reader.fieldnames)
        missing_headers = expected_headers - actual_headers
        if missing_headers:
            raise HTTPException(
                status_code=400, detail=f"Eksik CSV başlıkları: {', '.join(missing_headers)}"
            )

        imported = 0
        failed = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):  # Start from 2 (1 is header)
            try:
                # Validate required fields
                if not row.get("email") or not row.get("password"):
                    errors.append(f"Satır {row_num}: E-posta ve şifre gerekli")
                    failed += 1
                    continue

                # Build user data dictionary
                user_data = {
                    "email": row["email"].strip(),
                    "password": row["password"].strip(),
                    "centre": row.get("centre", "").strip(),
                    "category": row.get("visa_category", "").strip(),
                    "subcategory": row.get("visa_subcategory", "").strip(),
                    "first_name": row.get("first_name", "").strip(),
                    "last_name": row.get("last_name", "").strip(),
                    "phone": row.get("phone", "").strip(),
                }

                # Create user with repository
                await user_repo.create(user_data)

                imported += 1
                logger.info(
                    f"CSV Import: User created {row['email']} by {token_data.get('sub', 'unknown')}"
                )

            except ValidationError as e:
                failed += 1
                errors.append(f"Satır {row_num}: {str(e)}")
            except Exception as e:
                failed += 1
                error_msg = str(e)
                # Make error message more user-friendly
                if "UNIQUE constraint failed" in error_msg:
                    errors.append(
                        f"Satır {row_num}: E-posta zaten kayıtlı ({row.get('email', 'N/A')})"
                    )
                else:
                    errors.append(f"Satır {row_num}: {error_msg}")

        logger.info(
            f"CSV Import completed by {token_data.get('sub', 'unknown')}: "
            f"{imported} imported, {failed} failed"
        )

        return {
            "imported": imported,
            "failed": failed,
            "errors": errors[:10],  # Return first 10 errors only
            "message": f"{imported} kullanıcı eklendi, {failed} başarısız",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="CSV dosyası işlenirken hata oluştu")
