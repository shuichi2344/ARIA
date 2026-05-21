"""
Password strength validation for ARIA.
Enforces: min 6 chars, at least 1 uppercase, 1 number, 1 special character.
"""

import re
from typing import Tuple

PASSWORD_REQUIREMENTS = (
    "Password must be at least 6 characters and include "
    "an uppercase letter, a number, and a special character (!@#$%^&*...)."
)


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password meets strength requirements.
    
    Returns:
        (is_valid, error_message) — error_message is empty if valid.
    """
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must include at least one uppercase letter."
    
    if not re.search(r'[0-9]', password):
        return False, "Password must include at least one number."
    
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?~`]', password):
        return False, "Password must include at least one special character."
    
    return True, ""
