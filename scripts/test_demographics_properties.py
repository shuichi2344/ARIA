"""
Property-based tests for the demographics endpoint.

Feature: simulation-settings
Property 7: Demographics endpoint returns valid distributions

Validates: Requirements 6.1, 6.2, 6.4
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import sampled_from, text, characters
from fastapi.testclient import TestClient

from aria.api.main import app
from aria.external.dosm import DOSMClient


# Valid Penang districts from DOSMClient
VALID_DISTRICTS = DOSMClient.PENANG_DISTRICTS

# Expected keys in the response
EXPECTED_INCOME_KEYS = {"B40", "M40", "T20"}
EXPECTED_AGE_KEYS = {"20-29", "30-39", "40-49", "50-59", "60+"}

client = TestClient(app)


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(district=sampled_from(VALID_DISTRICTS))
def test_demographics_returns_valid_distributions(district: str):
    """
    Property 7: Demographics endpoint returns valid distributions

    For any valid Penang district name, the GET /api/demographics/{district}
    endpoint SHALL return income_distribution with B40, M40, T20 percentages
    that sum to approximately 100%, and age_distribution with all 6 age groups
    whose percentages sum to approximately 100%.

    **Validates: Requirements 6.1, 6.2, 6.4**

    Feature: simulation-settings, Property 7: Demographics endpoint returns valid distributions
    """
    response = client.get(f"/api/demographics/{district}")

    # Endpoint should return 200 for valid districts
    assert response.status_code == 200, (
        f"Expected 200 for district '{district}', got {response.status_code}: "
        f"{response.text}"
    )

    data = response.json()

    # Verify response structure
    assert "district" in data, "Response missing 'district' field"
    assert "income_distribution" in data, "Response missing 'income_distribution' field"
    assert "age_distribution" in data, "Response missing 'age_distribution' field"
    assert data["district"] == district

    # Verify income distribution has all expected keys
    income_dist = data["income_distribution"]
    assert set(income_dist.keys()) == EXPECTED_INCOME_KEYS, (
        f"Income distribution keys mismatch. "
        f"Expected {EXPECTED_INCOME_KEYS}, got {set(income_dist.keys())}"
    )

    # Verify each income group has a percentage field
    for key in EXPECTED_INCOME_KEYS:
        assert "percentage" in income_dist[key], (
            f"Income group '{key}' missing 'percentage' field"
        )
        assert isinstance(income_dist[key]["percentage"], (int, float)), (
            f"Income group '{key}' percentage is not numeric"
        )
        assert "description" in income_dist[key], (
            f"Income group '{key}' missing 'description' field"
        )

    # Assert income percentages sum to approximately 100%
    income_sum = sum(income_dist[k]["percentage"] for k in EXPECTED_INCOME_KEYS)
    assert abs(income_sum - 100.0) < 1.0, (
        f"Income percentages sum to {income_sum}, expected approximately 100%"
    )

    # Verify age distribution has all expected keys
    age_dist = data["age_distribution"]
    assert set(age_dist.keys()) == EXPECTED_AGE_KEYS, (
        f"Age distribution keys mismatch. "
        f"Expected {EXPECTED_AGE_KEYS}, got {set(age_dist.keys())}"
    )

    # Verify each age group has a percentage field
    for key in EXPECTED_AGE_KEYS:
        assert "percentage" in age_dist[key], (
            f"Age group '{key}' missing 'percentage' field"
        )
        assert isinstance(age_dist[key]["percentage"], (int, float)), (
            f"Age group '{key}' percentage is not numeric"
        )

    # Assert age group percentages sum to approximately 100%
    age_sum = sum(age_dist[k]["percentage"] for k in EXPECTED_AGE_KEYS)
    assert abs(age_sum - 100.0) < 1.0, (
        f"Age percentages sum to {age_sum}, expected approximately 100%"
    )


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(district=text(
    alphabet=characters(
        whitelist_categories=('L', 'N', 'P', 'S'),
        blacklist_characters='/?#&'
    ),
    min_size=1
).filter(lambda s: s.strip() != '' and s not in VALID_DISTRICTS))
def test_invalid_district_returns_400_with_available_districts(district: str):
    """
    Property 8: Invalid district error handling

    For any string that is not a valid Penang district name, the
    GET /api/demographics/{district} endpoint SHALL return HTTP 400
    with a message listing the available districts.

    **Validates: Requirements 6.3**

    Feature: simulation-settings, Property 8: Invalid district error handling
    """
    response = client.get(f"/api/demographics/{district}")

    # Endpoint should return 400 for invalid districts
    assert response.status_code == 400, (
        f"Expected 400 for invalid district '{district}', got {response.status_code}: "
        f"{response.text}"
    )

    data = response.json()

    # Response should contain a detail message
    assert "detail" in data, "Error response missing 'detail' field"

    # The detail message should list available districts
    detail = data["detail"]
    for valid_district in VALID_DISTRICTS:
        assert valid_district in detail, (
            f"Error detail should list available district '{valid_district}'. "
            f"Got: {detail}"
        )
