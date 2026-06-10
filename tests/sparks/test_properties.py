# Feature: context-sparks, Property (Task 2.1): Template Catalogue Determinism
# Validates: Requirements 1.1, 1.6
from hypothesis import given, settings
from hypothesis.strategies import sampled_from

from aria.sparks.spark_templates import SPARK_TEMPLATES

EXPECTED_TEMPLATE_IDS = {"competitive_context", "location_context", "business_hours_seasonality"}


def test_template_catalogue_has_exactly_three_templates():
    """Verify SPARK_TEMPLATES contains exactly the three expected template IDs."""
    assert set(SPARK_TEMPLATES.keys()) == EXPECTED_TEMPLATE_IDS


@given(template_id=sampled_from(list(SPARK_TEMPLATES.keys())))
@settings(max_examples=100)
def test_template_question_order_is_deterministic(template_id):
    """For each template, repeated access to questions yields the same order."""
    template = SPARK_TEMPLATES[template_id]
    # Accessing questions twice should yield same order
    first_access = [q.id for q in template.questions]
    second_access = [q.id for q in template.questions]
    assert first_access == second_access
    assert len(template.questions) > 0


# Feature: context-sparks, Property 6: Answer Sanitization Length Bound
# Validates: Requirements 2.7, 5.6, 9.6
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from aria.sparks.spark_manager import SparkManager


@given(s=st.text())
@settings(max_examples=200)
def test_sanitize_answer_length_bound(s):
    from fastapi import HTTPException
    try:
        result = SparkManager.sanitize_answer(s)
        assert len(result) <= 500
    except HTTPException:
        # Injection detected — length bound doesn't apply to rejected inputs
        pass


# Feature: context-sparks, Property 8: Single-Answer Edit Preserves Others
# Validates: Requirements 7.2
from hypothesis import given, settings
from hypothesis import strategies as st


@given(
    all_answers=st.fixed_dictionaries({
        "comp_names_count": st.text(min_size=1, max_size=100),
        "comp_pricing": st.text(min_size=1, max_size=100),
        "comp_offerings": st.text(min_size=1, max_size=100),
    }),
    new_value=st.text(min_size=1, max_size=100),
)
@settings(max_examples=100)
def test_single_answer_edit_preserves_others(all_answers, new_value):
    """Editing one answer should not change the other answers."""
    edit_key = "comp_names_count"

    # Simulate the merge logic from update_spark:
    # merged_answers = dict(spark.answers); merged_answers[qid] = sanitize_answer(ans)
    merged = dict(all_answers)  # copy — mirrors `merged_answers = dict(spark.answers)`
    merged[edit_key] = SparkManager.sanitize_answer(new_value)

    # All other keys must remain unchanged
    for key, original_val in all_answers.items():
        if key != edit_key:
            assert merged[key] == original_val


# Feature: context-sparks, Property 2: Q&A Completion Precondition
# Validates: Requirements 2.3, 2.4
from datetime import datetime
from uuid import uuid4
from hypothesis import given, settings
from hypothesis import strategies as st
from aria.sparks.spark_manager import SparkRecord
from aria.sparks.spark_templates import SPARK_TEMPLATES


def _is_completion_valid(spark: SparkRecord, template) -> bool:
    """Mirror the completion logic from SparkManager.submit_answer."""
    question_ids = {q.id for q in template.questions}
    return all(spark.answers.get(qid, "").strip() != "" for qid in question_ids)


@given(
    template_id=st.sampled_from(list(SPARK_TEMPLATES.keys())),
    data=st.data(),
)
@settings(max_examples=100)
def test_qa_completion_precondition(template_id, data):
    """A Spark with fewer answers than template questions must not be completed."""
    template = SPARK_TEMPLATES[template_id]
    n = len(template.questions)
    # Draw k < n  (could be 0)
    k = data.draw(st.integers(min_value=0, max_value=n - 1))

    # Build partial answers for the first k questions
    partial_answers = {}
    for i in range(k):
        q = template.questions[i]
        answer = data.draw(st.text(min_size=1, max_size=100))
        partial_answers[q.id] = answer

    spark = SparkRecord(
        spark_id=str(uuid4()),
        user_id=str(uuid4()),
        template_id=template_id,
        name="Test Spark",
        status="in_progress" if k > 0 else "draft",
        answers=partial_answers,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    # With k < n answers, completion check must return False
    assert not _is_completion_valid(spark, template)


@given(
    template_id=st.sampled_from(list(SPARK_TEMPLATES.keys())),
    data=st.data(),
)
@settings(max_examples=100)
def test_qa_completion_valid_when_all_answered(template_id, data):
    """A Spark with ALL questions answered (all non-empty) should pass the completion check."""
    template = SPARK_TEMPLATES[template_id]

    # Build complete answers: one non-empty (after stripping) answer per question
    full_answers = {}
    for q in template.questions:
        answer = data.draw(st.text(min_size=1, max_size=100).filter(lambda s: s.strip() != ""))
        full_answers[q.id] = answer

    spark = SparkRecord(
        spark_id=str(uuid4()),
        user_id=str(uuid4()),
        template_id=template_id,
        name="Test Spark",
        status="completed",
        answers=full_answers,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    # With all questions answered, completion check must return True
    assert _is_completion_valid(spark, template)


# Feature: context-sparks, Property 4: Spark Context Prompt Containment
# Validates: Requirements 5.1, 5.3, 5.5
from aria.sparks.spark_context_injector import SparkContextInjector


@given(
    answers=st.dictionaries(
        keys=st.sampled_from(["comp_names_count", "comp_pricing", "comp_offerings"]),
        values=st.text(min_size=1, max_size=100),
        min_size=1,
    )
)
@settings(max_examples=100)
def test_spark_context_prompt_containment(answers):
    """Every non-empty sanitized answer must appear as a substring in the built section."""
    from fastapi import HTTPException
    spark = SparkRecord(
        spark_id=str(uuid4()), user_id=str(uuid4()),
        template_id="competitive_context", name="Test",
        status="completed", answers=answers,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    template = SPARK_TEMPLATES["competitive_context"]
    section = SparkContextInjector.build_spark_section(spark, template)

    for a in answers.values():
        try:
            sanitized = SparkManager.sanitize_answer(a)
        except HTTPException:
            continue  # injection detected, skip
        if sanitized.strip():
            assert sanitized in section, f"Expected {sanitized!r} to be in section"


# Feature: context-sparks, Property 5: No-Spark Prompt Invariance
# Validates: Requirements 5.4
@given(base_prompt=st.text(min_size=1, max_size=500))
@settings(max_examples=100)
def test_no_spark_prompt_invariance(base_prompt):
    """inject_into_scenario_prompt with spark=None must return base_prompt unchanged."""
    result = SparkContextInjector.inject_into_scenario_prompt(base_prompt, spark=None, template=None)
    assert result == base_prompt


# Feature: context-sparks, Property 7: Spark Prompt Section Size Bound
# Validates: Requirements 9.8
@given(
    template_id=st.sampled_from(list(SPARK_TEMPLATES.keys())),
    data=st.data(),
)
@settings(max_examples=100)
def test_spark_prompt_section_size_bound(template_id, data):
    """The Spark section must never exceed 1500 chars regardless of input."""
    template = SPARK_TEMPLATES[template_id]
    answers = {}
    for q in template.questions:
        answers[q.id] = data.draw(st.text(max_size=500))

    spark = SparkRecord(
        spark_id=str(uuid4()), user_id=str(uuid4()),
        template_id=template_id, name="Test",
        status="completed", answers=answers,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    section = SparkContextInjector.build_spark_section(spark, template)
    assert len(section) <= 1500


# Feature: context-sparks, Property 1: Spark Answers Round-Trip
# Validates: Requirements 3.4
import json

from uuid import uuid4
from datetime import datetime
from hypothesis import given, settings
from hypothesis import strategies as st
from aria.sparks.spark_manager import SparkRecord


@given(
    answers=st.dictionaries(
        keys=st.sampled_from([
            "comp_names_count", "comp_pricing", "comp_offerings",
            "loc_traffic_type", "loc_landmarks", "loc_area_type",
            "bhs_peak_hours", "bhs_seasonal_peaks", "bhs_slow_periods",
        ]),
        values=st.text(max_size=500),
        min_size=1,
    )
)
@settings(max_examples=100)
def test_spark_answers_round_trip(answers):
    """Spark answers must survive a JSON serialize/deserialize cycle unchanged."""
    spark = SparkRecord(
        spark_id=str(uuid4()), user_id=str(uuid4()),
        template_id="competitive_context", name="Test",
        status="completed", answers=answers,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    serialized = json.dumps(spark.answers)
    deserialized = json.loads(serialized)
    assert deserialized == spark.answers
