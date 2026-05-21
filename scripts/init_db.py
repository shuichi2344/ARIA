"""
Database initialization script for ARIA.
Executes the initial schema migration on Supabase.
"""

import sys
from pathlib import Path
from supabase import create_client, Client
from aria.config import get_settings


def init_database():
    """Initialize the database schema."""
    settings = get_settings()
    
    print("Connecting to Supabase...")
    supabase: Client = create_client(
        str(settings.supabase_url),
        settings.supabase_key
    )
    
    # Read the migration file
    migration_file = Path("migrations/001_initial_schema.sql")
    if not migration_file.exists():
        print(f"Error: Migration file not found at {migration_file}")
        sys.exit(1)
    
    print(f"Reading migration from {migration_file}...")
    with open(migration_file, 'r') as f:
        sql_script = f.read()
    
    print("Executing migration...")
    try:
        # Note: Supabase Python client doesn't directly support raw SQL execution
        # You'll need to run this migration through Supabase Dashboard SQL Editor
        # or use psycopg2 with the database connection string
        print("\n" + "="*60)
        print("IMPORTANT: Please execute the following SQL in Supabase Dashboard:")
        print("="*60)
        print("\n1. Go to your Supabase project dashboard")
        print("2. Navigate to SQL Editor")
        print("3. Copy and paste the contents of migrations/001_initial_schema.sql")
        print("4. Click 'Run' to execute the migration")
        print("\n" + "="*60)
        
        # Alternative: Use psycopg2 if you have the connection string
        print("\nAlternatively, if you have psycopg2 installed:")
        print("You can use the database connection string from Supabase settings")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print("\nDatabase initialization instructions displayed.")
    print("After running the migration, your database will be ready!")


if __name__ == "__main__":
    init_database()
