"""
Response parsing utilities for LLM outputs.
Handles JSON extraction and validation from LLM responses.
"""

import json
import re
from typing import Dict, Any, List


class ParsingError(Exception):
    """Exception raised for parsing errors."""
    pass


def parse_json_response(response: str) -> Dict[str, Any]:
    """
    Parse JSON from LLM response, handling common formatting issues.
    Handles: markdown fences, thinking tags, truncated JSON, etc.

    Args:
        response: Raw LLM response text

    Returns:
        Parsed JSON dictionary

    Raises:
        ParsingError: If JSON cannot be parsed
    """
    # Strip any thinking tags before parsing (e.g. <think>...</think>)
    response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()

    # Fix common LLM JSON mistakes BEFORE any parsing attempts:
    # 1. \' is not valid JSON escape — replace with just '
    # 2. \_ and other invalid escapes — remove the backslash
    response = response.replace("\\'", "'")
    response = re.sub(r'\\(?!["\\/bfnrtu])', '', response)

    # Try direct JSON parsing first
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences: ```json...``` or ```...```
    # Handle both with and without newlines after the opening fence
    stripped = response.strip()
    if stripped.startswith('```'):
        # Remove opening fence (```json or ```)
        stripped = re.sub(r'^```(?:json|JSON)?[\s]*\n?', '', stripped, count=1)
        # Remove closing fence if present (anywhere at the end, even with trailing whitespace)
        stripped = re.sub(r'\n?```\s*$', '', stripped, count=1)
        stripped = stripped.strip()
        
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            # Try fixing common LLM JSON issues: control chars in strings
            try:
                # Remove control characters that break JSON (except \n \r \t)
                cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', stripped)
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
            # The JSON might be truncated after stripping fences — try brace matching below
            pass
    
    # Also handle fences that appear mid-response (e.g. after some preamble text)
    fence_match = re.search(r'```(?:json|JSON)?\s*\n?([\s\S]*?)\s*\n?```', response, re.DOTALL)
    if fence_match:
        content = fence_match.group(1).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

    # Try to find the outermost JSON object by matching braces (string-aware)
    first_brace = response.find('{')
    if first_brace != -1:
        depth = 0
        last_valid_end = -1
        in_string = False
        escape_next = False
        for i in range(first_brace, len(response)):
            ch = response[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    last_valid_end = i
                    break
        
        if last_valid_end != -1:
            candidate = response[first_brace:last_valid_end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        
        # JSON might be truncated — try to repair by closing open braces/brackets
        if depth > 0:
            truncated = response[first_brace:]
            repaired = _try_repair_truncated_json(truncated)
            if repaired is not None:
                return repaired

    # Try to find JSON array
    first_bracket = response.find('[')
    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        depth = 0
        for i in range(first_bracket, len(response)):
            if response[i] == '[':
                depth += 1
            elif response[i] == ']':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(response[first_bracket:i + 1])
                    except json.JSONDecodeError:
                        break

    raise ParsingError(f"Could not parse JSON from response: {response[:200]}...")


def _try_repair_truncated_json(text: str) -> Dict[str, Any] | None:
    """
    Attempt to repair truncated JSON by closing open structures.
    This handles the common case where max_tokens cuts off the response.
    
    Strategy: find the last complete scenario in the array and close everything.
    """
    # Try progressively removing content from the end and closing brackets
    # Look for the last complete object in a "scenarios" array
    
    # Find where scenarios array content might end cleanly
    # Look for the last "}," or "}" that could end a scenario object
    last_complete = -1
    
    # Try to find the last position where we have a complete scenario object
    # by looking for "},\n" or "}\n" patterns after "relevance_score"
    patterns = [
        r'\}\s*,\s*\{',  # between two scenario objects
        r'\}\s*\]',       # end of scenarios array
        r'"relevance_score"\s*:\s*\d+\s*\}',  # end of a scenario with relevance_score
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            last_complete = match.end()
    
    if last_complete == -1:
        return None
    
    # Try closing at various points
    for end_pos in [last_complete, len(text)]:
        candidate = text[:end_pos]
        
        # Count open braces and brackets
        open_braces = candidate.count('{') - candidate.count('}')
        open_brackets = candidate.count('[') - candidate.count(']')
        
        # Close them
        closing = ']' * max(0, open_brackets) + '}' * max(0, open_braces)
        
        try:
            result = json.loads(candidate + closing)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue
    
    return None


def parse_scenario_suggestions(response: str) -> Dict[str, Any]:
    """
    Parse scenario suggestion response.

    Args:
        response: LLM response

    Returns:
        Dictionary with analysis and scenarios

    Raises:
        ParsingError: If parsing fails
    """
    try:
        data = parse_json_response(response)

        if "scenarios" not in data:
            raise ParsingError("Response must contain 'scenarios' key")

        if not isinstance(data["scenarios"], list):
            raise ParsingError("'scenarios' must be an array")

        # Validate scenarios but be lenient — keep valid ones even if some are incomplete
        valid_scenarios = []
        for scenario in data["scenarios"]:
            required_fields = [
                "scenario_name", "scenario_type", "description",
                "parameters", "relevance_score"
            ]
            missing = [f for f in required_fields if f not in scenario]
            if missing:
                print(f"  [parser] Skipping incomplete scenario (missing: {missing})")
                continue

            try:
                score = float(scenario["relevance_score"])
                if not 0 <= score <= 100:
                    print(f"  [parser] Clamping relevance_score {score} to valid range")
                    scenario["relevance_score"] = max(0, min(100, score))
            except (ValueError, TypeError):
                scenario["relevance_score"] = 50  # Default if unparseable

            valid_scenarios.append(scenario)

        if not valid_scenarios:
            raise ParsingError("No valid scenarios found in response")

        data["scenarios"] = valid_scenarios
        return data

    except ParsingError:
        raise
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        raise ParsingError(f"Failed to parse scenario suggestions: {str(e)}")
