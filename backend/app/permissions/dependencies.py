from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.db import get_db
from app.models import Channel, Membership, Role

# Central role-action mapping based on permissions.md
ROLE_PERMISSIONS = {
    Role.OWNER.value: {
        "view_channel",
        "view_messages",
        "send_messages",
        "ask_bot",
        "view_files",
        "upload_files",
        "delete_own_file",
        "delete_any_file",
        "add_remove_members",
        "change_member_roles",
        "rename_channel",
        "delete_channel",
        "manage_workspace_owner",
    },
    Role.ADMIN.value: {
        "view_channel",
        "view_messages",
        "send_messages",
        "ask_bot",
        "view_files",
        "upload_files",
        "delete_own_file",
        "delete_any_file",
        "add_remove_members",
        "change_member_roles",
        "rename_channel",
    },
    Role.MEMBER.value: {
        "view_channel",
        "view_messages",
        "send_messages",
        "ask_bot",
        "view_files",
        "upload_files",
        "delete_own_file",
    },
    Role.READ_ONLY.value: {
        "view_channel",
        "view_messages",
        "ask_bot",
        "view_files",
    },
}


class RequireRole:
    def __init__(self, action: str):
        self.action = action

    async def __call__(
        self,
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Membership:
        # Extract channel_id from path parameters (try 'channel_id' first, fallback to 'id')
        channel_id_str = request.path_params.get("channel_id") or request.path_params.get("id")
        if not channel_id_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Channel ID is required for this operation",
            )

        try:
            channel_id = UUID(str(channel_id_str))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid channel ID format",
            )

        # 1. Validate that the channel exists in database
        channel_exists = await db.scalar(select(Channel).where(Channel.id == channel_id))
        if not channel_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found",
            )

        # 2. Check user's channel membership
        membership = await db.scalar(
            select(Membership).where(
                Membership.user_id == current_user.id,
                Membership.channel_id == channel_id,
            )
        )
        if not membership:
            # Maintain security confidentiality: return 404 for non-members
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found",
            )

        # 3. Check role authorization
        allowed_actions = ROLE_PERMISSIONS.get(membership.role, set())
        if self.action not in allowed_actions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )

        return membership


def require_role(action: str):
    return RequireRole(action)
