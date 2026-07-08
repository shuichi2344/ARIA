"""Response parsing utilities for LLM outputs."""
import json
import re
from typing import Dict, Any

class ParsingError(Exception):
    """Exception raised for parsing errors."""
    pass

def parse_json_response(response: str) -> Dict[str, Any]:
    """Parse JSON from LLM response, handling common formatting issues."""
    response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
    response = response.replace("\\'", "'")
    response = re.sub(r'\\(?!["\\/bfnrtu])', '', response)
    
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    stripped = response.strip()
    if stripped.startswith('`'):
        stripped = re.sub(r'^`(?:json|JSON)?[\s]*\n?', '', stripped, count=1)
        stripped = re.sub(r'\n?`\s*$', '', stripped, count=1)
        stripped = stripped.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    
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
    
    raise ParsingError(f"Could not parse JSON from response: {response[:200]}...")
