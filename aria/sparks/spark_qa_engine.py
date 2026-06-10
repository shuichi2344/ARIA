"""
SparkQAEngine — Conversational Q&A sequencing for Context Sparks.

Thin orchestration layer above SparkManager that drives the Q&A flow:
deciding which question to ask next and producing ARIA chat message text.
"""

from __future__ import annotations

from aria.sparks.spark_manager import QAState, SparkManager, SparkQuestion, SparkRecord  # noqa: F401
from aria.sparks.spark_templates import SPARK_TEMPLATES


class SparkQAEngine:
    """Drives the conversational Q&A flow for creating a Spark."""

    def __init__(self, spark_manager: SparkManager) -> None:
        self.spark_manager = spark_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_qa(
        self,
        user_id: str,
        template_id: str,
        session_id: str,
    ) -> QAState:
        """
        Create a new draft Spark and return the first question as a chat message.

        Returns QAState containing the spark_id, current question text,
        and the question index.
        """
        spark: SparkRecord = await self.spark_manager.create_spark(user_id, template_id)
        template = SPARK_TEMPLATES[template_id]
        first_question = template.questions[0]
        total = len(template.questions)

        return QAState(
            spark_id=spark.spark_id,
            status="draft",
            current_question=first_question,
            current_question_index=0,
            total_questions=total,
            aria_message=self.get_question_message(first_question, 0, total),
            validation_error=None,
        )

    async def process_answer(
        self,
        spark_id: str,
        user_id: str,
        raw_answer: str,
    ) -> QAState:
        """
        Submit an answer and return the next QAState.

        - If blank/whitespace-only, returns the same question with a validation error.
        - If all questions are answered after this submission, returns status=completed.
        - Otherwise, advances to the next unanswered question.
        """
        spark: SparkRecord = await self.spark_manager.get_spark(spark_id, user_id)
        template = SPARK_TEMPLATES[spark.template_id]
        total = len(template.questions)

        # Determine which question is currently unanswered (before submitting)
        current_idx, current_q = self._find_first_unanswered(spark, template)

        # Blank answer check
        if raw_answer.strip() == "":
            validation_msg = "Please provide a non-empty answer."
            return QAState(
                spark_id=spark_id,
                status=spark.status,
                current_question=current_q,
                current_question_index=current_idx,
                total_questions=total,
                aria_message=f"{validation_msg}\n\n{self.get_question_message(current_q, current_idx, total)}",
                validation_error=validation_msg,
            )

        # Submit the answer
        updated_spark: SparkRecord = await self.spark_manager.submit_answer(
            spark_id, user_id, current_q.id, raw_answer
        )

        # Completed?
        if updated_spark.status == "completed":
            return QAState(
                spark_id=spark_id,
                status="completed",
                current_question=None,
                current_question_index=total,
                total_questions=total,
                aria_message=(
                    f"Your '{updated_spark.name}' Spark is ready! "
                    "Activate it for this session to enrich your simulations, or save it for later."
                ),
                validation_error=None,
            )

        # Advance to the next unanswered question
        next_idx, next_q = self._find_first_unanswered(updated_spark, template)

        return QAState(
            spark_id=spark_id,
            status=updated_spark.status,
            current_question=next_q,
            current_question_index=next_idx,
            total_questions=total,
            aria_message=self.get_question_message(next_q, next_idx, total),
            validation_error=None,
        )

    def get_question_message(self, question: SparkQuestion, index: int, total: int) -> str:
        """
        Format a question as an ARIA chat message.

        Example: 'Question 2 of 4: What are your competitor prices?'
        """
        return f"Question {index + 1} of {total}: {question.text}"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_first_unanswered(
        spark: SparkRecord,
        template,
    ) -> tuple[int, SparkQuestion]:
        """
        Find the first question in the template that has no non-empty answer.

        Returns (index, SparkQuestion).  If all questions are answered this
        should not be called, but as a safe fallback the last question is
        returned.
        """
        for idx, question in enumerate(template.questions):
            if not spark.answers.get(question.id, "").strip():
                return idx, question

        # Fallback: all answered — return the last question (shouldn't reach here
        # in normal flow since status would be completed)
        last_idx = len(template.questions) - 1
        return last_idx, template.questions[last_idx]
