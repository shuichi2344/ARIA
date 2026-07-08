"""
Response parsing utilities for LLM outputs.
Handles JSON extraction and validation from LLM responses.
"""

import json
import re
from typing import Dict, Any


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
