"""VFS Account management routes for VFS-Bot web application."""

import csv
import io
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger

from src.repositories.account_pool_repository import AccountPoolRepository
from web.dependencies import get_vfs_account_repository, verify_jwt_token
from web.models.vfs_accounts import VFSAccountCreateRequest, VFSAccountModel, VFSAccountUpdateRequest

router = APIRouter(prefix="/vfs-accounts", tags=["vfs-accounts"])


@router.get("", response_model=List[VFSAccountModel])
async def get_vfs_accounts(
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    account_repo: AccountPoolRepository = Depends(get_vfs_account_repository),
):
    """Get all VFS accounts from database - requires authentication."""
    accounts_data = await account_repo.get_all_accounts()

    accounts = []
    for account in accounts_data:
        accounts.append(
            VFSAccountModel(
                id=account["id"],
                email=account["email"],
                phone=account.get("phone") or "",
                is_active=bool(account["is_active"]),
                created_at=str(account["created_at"]),
                updated_at=str(account["updated_at"]),
            )
        )

    return accounts


@router.post("", response_model=VFSAccountModel)
async def create_vfs_account(
    account: VFSAccountCreateRequest,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    account_repo: AccountPoolRepository = Depends(get_vfs_account_repository),
):
    """Create a new VFS account - requires authentication."""
    try:
        account_id = await account_repo.create_account(
            email=account.email,
            password=account.password,
            phone=account.phone,
        )

        created_account = await account_repo.get_account_by_id(account_id, decrypt=False)

        if not created_account:
            raise HTTPException(status_code=500, detail="Failed to retrieve created account")

        # Apply is_active if not default
        if not account.is_active:
            await account_repo.update_account(account_id, {"is_active": False})
            created_account["is_active"] = False

        logger.info(f"VFS account created: {account.email} by {token_data.get('sub', 'unknown')}")

        return VFSAccountModel(
            id=created_account["id"],
            email=created_account["email"],
            phone=created_account.get("phone") or "",
            is_active=bool(created_account["is_active"]),
            created_at=str(created_account["created_at"]),
            updated_at=str(created_account["updated_at"]),
        )

    except Exception as e:
        logger.error(f"Error creating VFS account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create VFS account")


@router.put("/{account_id}", response_model=VFSAccountModel)
async def update_vfs_account(
    account_id: int,
    account_update: VFSAccountUpdateRequest,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    account_repo: AccountPoolRepository = Depends(get_vfs_account_repository),
):
    """Update a VFS account - requires authentication."""
    try:
        update_data = account_update.model_dump(exclude_none=True)

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        updated = await account_repo.update_account(account_id, update_data)

        if not updated:
            raise HTTPException(status_code=404, detail="VFS account not found")

        updated_account = await account_repo.get_account_by_id(account_id, decrypt=False)

        if not updated_account:
            raise HTTPException(status_code=404, detail="VFS account not found after update")

        logger.info(
            f"VFS account updated: {updated_account['email']} by {token_data.get('sub', 'unknown')}"
        )

        return VFSAccountModel(
            id=updated_account["id"],
            email=updated_account["email"],
            phone=updated_account.get("phone") or "",
            is_active=bool(updated_account["is_active"]),
            created_at=str(updated_account["created_at"]),
            updated_at=str(updated_account["updated_at"]),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating VFS account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update VFS account")


@router.delete("/{account_id}")
async def delete_vfs_account(
    account_id: int,
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    account_repo: AccountPoolRepository = Depends(get_vfs_account_repository),
):
    """Delete (deactivate) a VFS account - requires authentication."""
    try:
        account = await account_repo.get_account_by_id(account_id, decrypt=False)

        if not account:
            raise HTTPException(status_code=404, detail="VFS account not found")

        deleted = await account_repo.deactivate_account(account_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="VFS account not found")

        logger.info(
            f"VFS account deactivated: {account['email']} by {token_data.get('sub', 'unknown')}"
        )
        return {"message": "VFS account deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting VFS account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete VFS account")


@router.patch("/{account_id}", response_model=VFSAccountModel)
async def toggle_vfs_account_status(
    account_id: int,
    status_update: Dict[str, bool],
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    account_repo: AccountPoolRepository = Depends(get_vfs_account_repository),
):
    """Toggle VFS account active status - requires authentication."""
    try:
        if "is_active" not in status_update:
            raise HTTPException(status_code=400, detail="is_active field required")

        updated = await account_repo.update_account(account_id, {"is_active": status_update["is_active"]})

        if not updated:
            raise HTTPException(status_code=404, detail="VFS account not found")

        updated_account = await account_repo.get_account_by_id(account_id, decrypt=False)
        if not updated_account:
            raise HTTPException(status_code=404, detail="VFS account not found after update")

        logger.info(
            f"VFS account status toggled: {updated_account['email']} -> {status_update['is_active']} "
            f"by {token_data.get('sub', 'unknown')}"
        )

        return VFSAccountModel(
            id=updated_account["id"],
            email=updated_account["email"],
            phone=updated_account.get("phone") or "",
            is_active=bool(updated_account["is_active"]),
            created_at=str(updated_account["created_at"]),
            updated_at=str(updated_account["updated_at"]),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling VFS account status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to toggle VFS account status")


@router.post("/import")
async def import_vfs_accounts_csv(
    file: UploadFile = File(...),
    token_data: Dict[str, Any] = Depends(verify_jwt_token),
    account_repo: AccountPoolRepository = Depends(get_vfs_account_repository),
):
    """
    Import VFS accounts from CSV file - requires authentication.

    CSV Format:
    email,password,phone
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Sadece CSV dosyası kabul edilir")

    try:
        content = await file.read()

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

        reader = csv.DictReader(io.StringIO(text))

        expected_headers = {"email", "password", "phone"}
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

        for row_num, row in enumerate(reader, start=2):
            try:
                if not row.get("email") or not row.get("password"):
                    errors.append(f"Satır {row_num}: E-posta ve şifre gerekli")
                    failed += 1
                    continue

                await account_repo.create_account(
                    email=row["email"].strip(),
                    password=row["password"].strip(),
                    phone=row.get("phone", "").strip(),
                )

                imported += 1
                logger.info(
                    f"CSV Import: VFS account created {row['email']} by {token_data.get('sub', 'unknown')}"
                )

            except Exception as e:
                failed += 1
                error_msg = str(e)
                if "UNIQUE constraint failed" in error_msg or "duplicate key" in error_msg.lower():
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
            "errors": errors[:10],
            "message": f"{imported} VFS hesabı eklendi, {failed} başarısız",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing CSV: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="CSV dosyası işlenirken hata oluştu")
