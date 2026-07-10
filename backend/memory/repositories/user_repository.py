"""User repository for SQLite memory."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.memory.models import UserORM, utc_now


class UserRepository:
    """Persistence operations for users."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_user(self, *, external_user_key: str | None = None) -> UserORM:
        user = UserORM(external_user_key=external_user_key)
        self._session.add(user)
        self._session.flush()
        return user

    def get_user(self, user_id: str) -> UserORM | None:
        return self._session.get(UserORM, user_id)

    def get_by_external_user_key(self, external_user_key: str) -> UserORM | None:
        return self._session.scalar(
            select(UserORM).where(UserORM.external_user_key == external_user_key)
        )

    def get_or_create_by_external_user_key(self, external_user_key: str) -> UserORM:
        existing = self.get_by_external_user_key(external_user_key)
        if existing is not None:
            return existing
        return self.create_user(external_user_key=external_user_key)

    def update_last_active_at(self, user_id: str) -> UserORM:
        user = self._require_user(user_id)
        user.last_active_at = utc_now()
        user.updated_at = utc_now()
        self._session.flush()
        return user

    def delete_user(self, user_id: str) -> None:
        user = self._require_user(user_id)
        self._session.delete(user)
        self._session.flush()

    def _require_user(self, user_id: str) -> UserORM:
        user = self.get_user(user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        return user
