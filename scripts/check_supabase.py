"""
Supabase verification script for ARIA.
Checks if Supabase connection works and if tables are created.
"""

import sys
import os
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aria.database.connection import check_connection, get_session
from aria.database.models import User, BusinessProfile, Archetype, Scenario, Simulation
from sqlalchemy import text


async def check_supabase():
    """Check Supabase connection and database schema."""
    print("=" * 60)
    print("ARIA - Supabase Verification")
    print("=" * 60)
    
    # Show configuration
    from aria.config import get_settings
    settings = get_settings()
    supabase_url = str(settings.supabase_url).rstrip("/")
    
    print(f"\nConfiguration:")
    print(f"  Supabase URL: {supabase_url}")
    
    # Extract project reference
    host = supabase_url.replace("https://", "").replace("http://", "")
    project_ref = host.split(".")[0]
    db_host = f"db.{project_ref}.supabase.co"
    
    print(f"  Project Ref: {project_ref}")
    print(f"  Database Host: {db_host}")
    print(f"  Database Port: 5432")
    print(f"  Database Name: postgres")
    print(f"  Database User: postgres")
    
    # Check 1: Basic connection
    print("\n1. Checking database connection...")
    print(f"   Attempting to connect to: {db_host}:5432")
    
    try:
        is_connected = await check_connection()
        if is_connected:
            print("   ✓ Database connection successful!")
        else:
            print("   ✗ Database connection failed!")
            print("\n   Troubleshooting steps:")
            print("   1. Verify your Supabase project is active")
            print("   2. Check if database pooler is enabled in Supabase Dashboard")
            print("   3. Verify SUPABASE_DB_PASSWORD is correct")
            print("   4. Try connecting from Supabase Dashboard → Database → Connection")
            return False
    except Exception as e:
        print(f"   ✗ Connection error: {e}")
        print(f"\n   Error type: {type(e).__name__}")
        
        if "getaddrinfo failed" in str(e):
            print("\n   This error means the database hostname cannot be resolved.")
            print("   Possible causes:")
            print("   1. Your Supabase project might be paused or deleted")
            print("   2. Network/firewall blocking the connection")
            print("   3. Incorrect project reference in SUPABASE_URL")
            print(f"\n   Expected hostname: {db_host}")
            print(f"   Please verify this hostname exists and is accessible")
        elif "password authentication failed" in str(e):
            print("\n   The database password is incorrect.")
            print("   Please check SUPABASE_DB_PASSWORD in your .env file")
        elif "timeout" in str(e).lower():
            print("\n   Connection timeout - network or firewall issue")
            print("   Check your internet connection and firewall settings")
        
        print("\n   To find your correct credentials:")
        print("   1. Go to Supabase Dashboard → Settings → Database")
        print("   2. Look for 'Connection string' section")
        print("   3. Use the password you set when creating the project")
        
        return False
    
    # Check 2: Verify tables exist
    print("\n2. Checking if database tables exist...")
    try:
        async with get_session() as session:
            # Check for main tables
            tables_to_check = [
                'users',
                'business_profiles',
                'archetypes',
                'scenarios',
                'simulations',
                'simulation_events',
                'agent_interactions',
                'simulation_analysis',
                'market_impact_reports',
                'error_logs'
            ]
            
            missing_tables = []
            for table_name in tables_to_check:
                result = await session.execute(
                    text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')")
                )
                exists = result.scalar()
                if exists:
                    print(f"   ✓ Table '{table_name}' exists")
                else:
                    print(f"   ✗ Table '{table_name}' missing")
                    missing_tables.append(table_name)
            
            if missing_tables:
                print(f"\n   ✗ Missing tables: {', '.join(missing_tables)}")
                print("\n   To create tables:")
                print("   1. Go to your Supabase Dashboard")
                print("   2. Navigate to SQL Editor")
                print("   3. Copy and paste the contents of migrations/001_initial_schema.sql")
                print("   4. Run the SQL script")
                return False
            else:
                print("\n   ✓ All required tables exist!")
    except Exception as e:
        print(f"   ✗ Error checking tables: {e}")
        return False
    
    # Check 3: Test basic CRUD operations
    print("\n3. Testing basic database operations...")
    try:
        async with get_session() as session:
            # Try to query users table (should be empty initially)
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            print(f"   ✓ Can query database (found {user_count} users)")
            
            # Try to query business_profiles table
            result = await session.execute(text("SELECT COUNT(*) FROM business_profiles"))
            profile_count = result.scalar()
            print(f"   ✓ Can query business_profiles (found {profile_count} profiles)")
            
    except Exception as e:
        print(f"   ✗ Error testing operations: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✓ All checks passed! Supabase is ready for ARIA.")
    print("=" * 60)
    return True


def main():
    """Main entry point."""
    try:
        result = asyncio.run(check_supabase())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
