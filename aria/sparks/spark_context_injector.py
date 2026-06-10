"""
SparkContextInjector — Prompt serialization and injection for Context Sparks.

Builds a labelled Markdown section from an active Spark's answers and injects
it into the scenario suggestion prompt and LLM agent system prompt.

This module is purely additive: when spark is None both inject methods return
the base prompt byte-for-byte unchanged.
"""

from typing import Optional

from aria.sparks.spark_manager import SparkManager, SparkRecord
from aria.sparks.spark_templates import SparkTemplate


class SparkContextInjector:
    """
    Pure-static helper that serializes an active Spark into a labelled
    Markdown prompt section and injects it into existing prompt strings.
    """

    MAX_SPARK_SECTION_CHARS = 1500

    @staticmethod
    def build_spark_section(
        spark: Optional[SparkRecord],
        template: Optional[SparkTemplate],
    ) -> str:
        """
        Serialize a Spark's answers into a labelled Markdown section.

        Format::

            ## Additional Business Context (Spark: <name>)
            **Template:** <template.name>

            **<question_label>:** <answer>
            ...

        Rules:
        - Returns ``""`` immediately if spark or template is None.
        - Only includes questions that have a non-empty answer (after stripping).
        - Sanitizes each answer via ``SparkManager.sanitize_answer``.
        - Truncates the full section string to ``MAX_SPARK_SECTION_CHARS``
          (1 500 chars) if it would exceed that limit.
        """
        if spark is None or template is None:
            return ""

        lines = [
            f"## Additional Business Context (Spark: {spark.name})",
            f"**Template:** {template.name}",
            "",
        ]

        for question in template.questions:
            raw_answer = spark.answers.get(question.id, "")
            if not raw_answer or not raw_answer.strip():
                continue
            sanitized = SparkManager.sanitize_answer(raw_answer)
            if not sanitized:
                continue
            lines.append(f"**{question.label}:** {sanitized}")

        section = "\n".join(lines)

        # Truncate to MAX_SPARK_SECTION_CHARS if necessary
        if len(section) > SparkContextInjector.MAX_SPARK_SECTION_CHARS:
            section = section[: SparkContextInjector.MAX_SPARK_SECTION_CHARS]

        return section

    @staticmethod
    def inject_into_scenario_prompt(
        base_prompt: str,
        spark: Optional[SparkRecord],
        template: Optional[SparkTemplate],
    ) -> str:
        """
        Append the Spark section to an existing scenario suggestion prompt.

        Returns ``base_prompt`` unchanged (byte-for-byte) when ``spark`` is
        ``None`` or when the built section is empty.
        """
        if spark is None:
            return base_prompt

        section = SparkContextInjector.build_spark_section(spark, template)
        if not section:
            return base_prompt

        return base_prompt + "\n" + section

    @staticmethod
    def inject_into_system_prompt(
        base_system_prompt: str,
        spark: Optional[SparkRecord],
        template: Optional[SparkTemplate],
    ) -> str:
        """
        Append the Spark section to an LLM agent system prompt.

        Returns ``base_system_prompt`` unchanged (byte-for-byte) when
        ``spark`` is ``None`` or when the built section is empty.
        """
        if spark is None:
            return base_system_prompt

        section = SparkContextInjector.build_spark_section(spark, template)
        if not section:
            return base_system_prompt

        return base_system_prompt + "\n" + section
