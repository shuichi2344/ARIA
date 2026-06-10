"""
SparkManager — CRUD and activation logic for Context Sparks.

Responsible for all DB-level operations and session activation/deactivation.
All DB access uses the existing SupabaseClient REST pattern.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

import aiohttp
from fastapi import HTTPException
from pydantic import BaseModel, Field

from aria.database.supabase_client import SupabaseClient
from aria.sparks.spark_templates import SPARK_TEMPLATES, SparkQuestion, SparkTemplate  # noqa: F401 (re-exported)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SparkRecord(BaseModel):
    """Represents a single persisted Spark record from the database."""

    spark_id: str
    user_id: str
    template_id: str
    name: str
    status: Literal["draft", "in_progress", "completed"]
    answers: Dict[str, str]
    created_at: datetime
    updated_at: datetime


class QAState(BaseModel):
    """State returned by the Q&A engine after each answer submission or session start."""

    spark_id: str
    status: Literal["draft", "in_progress", "completed"]
    current_question: Optional[SparkQuestion]
    current_question_index: int
    total_questions: int
    aria_message: str
    validation_error: Optional[str]


class SparkCreateRequest(BaseModel):
    """Request body for POST /api/sparks."""

    model_config = {"extra": "forbid"}

    user_id: str = Field(..., max_length=100)
    template_id: str = Field(..., max_length=50)
    name: Optional[str] = Field(None, max_length=100)


class SparkAnswerRequest(BaseModel):
    """Request body for POST /api/sparks/{spark_id}/answer."""

    model_config = {"extra": "forbid"}

    user_id: str = Field(..., max_length=100)
    question_id: str = Field(..., max_length=100)
    answer_text: str = Field(..., max_length=510)


class SparkActivateRequest(BaseModel):
    """Request body for POST /api/sparks/{spark_id}/activate."""

    model_config = {"extra": "forbid"}

    user_id: str = Field(..., max_length=100)
    session_id: str = Field(..., max_length=100)


class SparkUpdateRequest(BaseModel):
    """Request body for PATCH /api/sparks/{spark_id}."""

    model_config = {"extra": "forbid"}

    user_id: str = Field(..., max_length=100)
    name: Optional[str] = Field(None, max_length=100)
    answer_updates: Optional[Dict[str, str]] = None


# ---------------------------------------------------------------------------
# SparkManager
# ---------------------------------------------------------------------------


class SparkManager:
    """Service layer for Spark CRUD operations and session activation."""

    def __init__(self, supabase: SupabaseClient) -> None:
        self.supabase = supabase

    # ------------------------------------------------------------------
    # Template catalogue
    # ------------------------------------------------------------------

    async def get_templates(self) -> List[SparkTemplate]:
        """Return the three built-in templates with their ordered questions."""
        return list(SPARK_TEMPLATES.values())

    # ------------------------------------------------------------------
    # Spark CRUD
    # ------------------------------------------------------------------

    async def create_spark(
        self,
        user_id: str,
        template_id: str,
        name: Optional[str] = None,
    ) -> SparkRecord:
        """
        Create a new Spark in status=draft.
        Auto-generates name from template if not provided.
        """
        if template_id not in SPARK_TEMPLATES:
            raise HTTPException(status_code=400, detail=f"Unknown template_id: {template_id!r}.")

        spark_name = name if name is not None else SPARK_TEMPLATES[template_id].name

        url = self.supabase.base_url + "/rest/v1/sparks"
        data = {
            "user_id": user_id,
            "template_id": template_id,
            "name": spark_name,
            "status": "draft",
            "answers": {},
        }
        headers = {**self.supabase.headers, "Prefer": "return=representation"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                if response.status in (200, 201):
                    result = await response.json()
                    record = result[0] if isinstance(result, list) else result
                    return SparkRecord(**record)
                error_text = await response.text()
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create spark: {error_text}",
                )

    async def get_spark(self, spark_id: str, user_id: str) -> SparkRecord:
        """Fetch a Spark by ID, enforcing owner check (403 if mismatch)."""
        url = self.supabase.base_url + f"/rest/v1/sparks?spark_id=eq.{spark_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.supabase.headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=500,
                        detail=f"DB error fetching spark: {error_text}",
                    )
                result = await response.json()

        if not result:
            raise HTTPException(status_code=404, detail="Spark not found.")

        record = result[0]
        if record["user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this Spark.",
            )

        return SparkRecord(**record)

    async def list_sparks(self, user_id: str) -> List[SparkRecord]:
        """Return all Sparks for a user, ordered by updated_at DESC."""
        url = (
            self.supabase.base_url
            + f"/rest/v1/sparks?user_id=eq.{user_id}&order=updated_at.desc"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.supabase.headers) as response:
                if response.status != 200:
                    return []
                result = await response.json()

        return [SparkRecord(**row) for row in result]

    async def submit_answer(
        self,
        spark_id: str,
        user_id: str,
        question_id: str,
        answer_text: str,
    ) -> SparkRecord:
        """
        Store an answer for the given question.
        - Validates ownership
        - Sanitizes answer text (sanitize_text + check_for_injection)
        - Truncates to 500 chars
        - Advances question index; updates status to completed when all answered
        - Returns updated SparkRecord
        """
        spark = await self.get_spark(spark_id, user_id)

        sanitized = SparkManager.sanitize_answer(answer_text)

        # Update answers dict
        spark.answers[question_id] = sanitized

        # Determine new status
        template = SPARK_TEMPLATES.get(spark.template_id)
        if template is None:
            # Unknown template — just mark in_progress
            new_status: Literal["draft", "in_progress", "completed"] = "in_progress"
        else:
            question_ids = {q.id for q in template.questions}
            all_answered = all(
                spark.answers.get(qid, "").strip() != "" for qid in question_ids
            )
            if all_answered:
                new_status = "completed"
            else:
                new_status = "in_progress"

        patch_url = self.supabase.base_url + f"/rest/v1/sparks?spark_id=eq.{spark_id}"
        patch_data = {
            "answers": spark.answers,
            "status": new_status,
            "updated_at": "now()",
        }
        headers = {**self.supabase.headers, "Prefer": "return=representation"}

        async with aiohttp.ClientSession() as session:
            async with session.patch(patch_url, json=patch_data, headers=headers) as response:
                if response.status in (200, 204):
                    result = await response.json()
                    if isinstance(result, list) and result:
                        return SparkRecord(**result[0])
                    # If 204 or empty, re-fetch
                    return await self.get_spark(spark_id, user_id)
                error_text = await response.text()
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update spark answers: {error_text}",
                )

    async def update_spark(
        self,
        spark_id: str,
        user_id: str,
        updates: SparkUpdateRequest,
    ) -> SparkRecord:
        """Partial update: name, individual answer overrides, etc."""
        spark = await self.get_spark(spark_id, user_id)

        patch_data: Dict = {"updated_at": "now()"}

        if updates.name is not None:
            patch_data["name"] = updates.name

        if updates.answer_updates is not None:
            merged_answers = dict(spark.answers)
            for qid, ans in updates.answer_updates.items():
                merged_answers[qid] = SparkManager.sanitize_answer(ans)
            patch_data["answers"] = merged_answers

        patch_url = self.supabase.base_url + f"/rest/v1/sparks?spark_id=eq.{spark_id}"
        headers = {**self.supabase.headers, "Prefer": "return=representation"}

        async with aiohttp.ClientSession() as session:
            async with session.patch(patch_url, json=patch_data, headers=headers) as response:
                if response.status in (200, 204):
                    result = await response.json()
                    if isinstance(result, list) and result:
                        return SparkRecord(**result[0])
                    return await self.get_spark(spark_id, user_id)
                error_text = await response.text()
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update spark: {error_text}",
                )

    async def delete_spark(self, spark_id: str, user_id: str) -> None:
        """
        Permanently remove a Spark.
        The ON DELETE SET NULL FK on chat_sessions.active_spark_id
        automatically clears the Spark from any session it was active in.
        """
        # Ownership check
        await self.get_spark(spark_id, user_id)

        delete_url = self.supabase.base_url + f"/rest/v1/sparks?spark_id=eq.{spark_id}"

        async with aiohttp.ClientSession() as session:
            async with session.delete(delete_url, headers=self.supabase.headers) as response:
                if response.status not in (200, 204):
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to delete spark: {error_text}",
                    )

    # ------------------------------------------------------------------
    # Session activation
    # ------------------------------------------------------------------

    async def activate_spark(
        self,
        spark_id: str,
        session_id: str,
        user_id: str,
    ) -> None:
        """
        Set active_spark_id on the chat session to this Spark.
        A single UPDATE replaces any previously active Spark.
        Raises 422 if the Spark status is not 'completed'.
        """
        spark = await self.get_spark(spark_id, user_id)

        if spark.status != "completed":
            raise HTTPException(
                status_code=422,
                detail="Spark must be completed before activation.",
            )

        patch_url = (
            self.supabase.base_url
            + f"/rest/v1/chat_sessions?session_id=eq.{session_id}"
        )
        patch_data = {"active_spark_id": spark_id}
        headers = {**self.supabase.headers, "Prefer": "return=minimal"}

        async with aiohttp.ClientSession() as session_:
            async with session_.patch(patch_url, json=patch_data, headers=headers) as response:
                if response.status not in (200, 204):
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to activate spark: {error_text}",
                    )

    async def deactivate_spark(self, session_id: str) -> None:
        """Set active_spark_id = NULL on the chat session."""
        patch_url = (
            self.supabase.base_url
            + f"/rest/v1/chat_sessions?session_id=eq.{session_id}"
        )
        patch_data = {"active_spark_id": None}
        headers = {**self.supabase.headers, "Prefer": "return=minimal"}

        async with aiohttp.ClientSession() as session:
            async with session.patch(patch_url, json=patch_data, headers=headers) as response:
                if response.status not in (200, 204):
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to deactivate spark: {error_text}",
                    )

    async def get_active_spark(self, session_id: str) -> Optional[SparkRecord]:
        """
        Read active_spark_id from chat_sessions, then fetch the sparks row.
        Returns None if active_spark_id is NULL or the Spark no longer exists.
        """
        session_url = (
            self.supabase.base_url
            + f"/rest/v1/chat_sessions?session_id=eq.{session_id}&select=active_spark_id"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(session_url, headers=self.supabase.headers) as response:
                if response.status != 200:
                    return None
                result = await response.json()

        if not result:
            return None

        active_spark_id = result[0].get("active_spark_id")
        if not active_spark_id:
            return None

        # Fetch the Spark row directly (skip ownership check — internal use)
        spark_url = (
            self.supabase.base_url
            + f"/rest/v1/sparks?spark_id=eq.{active_spark_id}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(spark_url, headers=self.supabase.headers) as response:
                if response.status != 200:
                    return None
                spark_result = await response.json()

        if not spark_result:
            return None  # Spark was deleted (FK set to NULL but row gone)

        return SparkRecord(**spark_result[0])

    # ------------------------------------------------------------------
    # Sanitization
    # ------------------------------------------------------------------

    @staticmethod
    def sanitize_answer(s: str) -> str:
        """
        Sanitize a free-text answer:
        - Applies sanitize_text and check_for_injection from aria.api.security
        - Truncates to 500 characters
        """
        from aria.api.security import check_for_injection, sanitize_text

        cleaned = sanitize_text(s)
        # check_for_injection raises HTTPException(400) on injection patterns;
        # let it propagate so the API layer returns a 400 response.
        check_for_injection(cleaned)
        return cleaned[:500]
