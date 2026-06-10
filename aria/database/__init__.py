"""
Database layer for ARIA.
Uses the SupabaseClient REST client for all database operations.
"""

from aria.database.supabase_client import SupabaseClient

__all__ = [
    "SupabaseClient",
]
