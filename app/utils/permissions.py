from fastapi import Depends, HTTPException, status

from app.database import ROLE_ADMIN, ROLE_TECHNICIAN, ROLE_WAREHOUSE, ROLE_RECEPTION
from app.utils.auth import get_current_user


def require_role(*allowed_roles: str):
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user.role == ROLE_ADMIN:
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Insufficient Role Permissions",
            )
        return current_user
    return role_checker


require_admin = require_role(ROLE_ADMIN)
require_reception = require_role(ROLE_RECEPTION, ROLE_ADMIN)
require_technician = require_role(ROLE_TECHNICIAN, ROLE_ADMIN)
require_warehouse = require_role(ROLE_WAREHOUSE, ROLE_ADMIN)
require_warehouse_or_admin = require_role(ROLE_WAREHOUSE, ROLE_ADMIN)
require_reception_or_admin = require_role(ROLE_RECEPTION, ROLE_ADMIN)
