"""Profile fact repository for SQLite memory."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.memory.models import UserProfileFactORM, utc_now


class ProfileRepository:
    """Persistence operations for flexible profile facts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_profile_fact(
        self,
        *,
        user_id: str,
        field_name: str,
        value: Any,
        source: str,
        is_confirmed: bool,
    ) -> UserProfileFactORM:
        existing = self._get_fact_row(user_id=user_id, field_name=field_name)
        if existing is None:
            fact = UserProfileFactORM(
                user_id=user_id,
                field_name=field_name,
                value_json=value,
                source=source,
                is_confirmed=is_confirmed,
            )
            self._session.add(fact)
            self._session.flush()
            return fact

        if existing.is_confirmed and not is_confirmed:
            return existing

        existing.value_json = value
        existing.source = source
        existing.is_confirmed = is_confirmed
        existing.updated_at = utc_now()
        self._session.flush()
        return existing

    def get_all_profile_facts(self, user_id: str) -> list[UserProfileFactORM]:
        return list(
            self._session.scalars(
                select(UserProfileFactORM)
                .where(UserProfileFactORM.user_id == user_id)
                .order_by(UserProfileFactORM.field_name)
            )
        )

    def get_selected_profile_facts(
        self,
        *,
        user_id: str,
        field_names: list[str],
    ) -> list[UserProfileFactORM]:
        if not field_names:
            return []
        return list(
            self._session.scalars(
                select(UserProfileFactORM)
                .where(UserProfileFactORM.user_id == user_id)
                .where(UserProfileFactORM.field_name.in_(field_names))
                .order_by(UserProfileFactORM.field_name)
            )
        )

    def delete_profile_fact(self, *, user_id: str, field_name: str) -> None:
        self._session.execute(
            delete(UserProfileFactORM)
            .where(UserProfileFactORM.user_id == user_id)
            .where(UserProfileFactORM.field_name == field_name)
        )
        self._session.flush()

    def clear_profile_facts(self, user_id: str) -> None:
        self._session.execute(
            delete(UserProfileFactORM).where(UserProfileFactORM.user_id == user_id)
        )
        self._session.flush()

    def _get_fact_row(
        self,
        *,
        user_id: str,
        field_name: str,
    ) -> UserProfileFactORM | None:
        return self._session.scalar(
            select(UserProfileFactORM)
            .where(UserProfileFactORM.user_id == user_id)
            .where(UserProfileFactORM.field_name == field_name)
        )
