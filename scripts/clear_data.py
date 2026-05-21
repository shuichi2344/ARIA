"""
Clear all data from database tables without dropping the tables.
Useful for cleaning up test data while keeping the schema intact.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aria.database.connection import get_engine
from sqlalchemy import text


async def clear_all_data():
    """Clear all data from all tables."""
    engine = get_engine()
    
    print("=" * 60)
    print("ARIA - Clear All Data")
    print("=" * 60)
    print("\n⚠️  WARNING: This will delete ALL data from the database!")
    print("   Tables will remain, but all records will be deleted.")
    
    # Ask for confirmation
    response = input("\n   Type 'yes' to confirm: ").strip().lower()
    
    if response != 'yes':
        print("\n   ✗ Operation cancelled")
        return
    
    async with engine.begin() as conn:
        print("\n   Clearing data from all tables...")
        
        try:
            # Delete in reverse order of dependencies to avoid foreign key issues
            tables = [
                "market_impact_reports",
                "simulation_analysis",
                "agent_interactions",
                "simulation_events",
                "simulations",
                "scenarios",
                "archetypes",
                "business_profiles",
                "error_logs",
                "users"
            ]
            
            total_deleted = 0
            
            for table in tables:
                result = await conn.execute(text(f"DELETE FROM {table}"))
                deleted = result.rowcount
                total_deleted += deleted
                print(f"      ✓ {table}: {deleted} records deleted")
            
            print(f"\n   ✓ Total records deleted: {total_deleted}")
            
        except Exception as e:
            print(f"\n   ✗ Error clearing data: {e}")
            return
    
    print("\n" + "=" * 60)
    print("✓ All data cleared successfully!")
    print("=" * 60)
    print("\n   Database tables are intact and ready for new data.")
    
    await engine.dispose()


async def clear_specific_tables(table_names: list):
    """Clear data from specific tables only."""
    engine = get_engine()
    
    print("=" * 60)
    print("ARIA - Clear Specific Tables")
    print("=" * 60)
    print(f"\n   Tables to clear: {', '.join(table_names)}")
    
    # Ask for confirmation
    response = input("\n   Type 'yes' to confirm: ").strip().lower()
    
    if response != 'yes':
        print("\n   ✗ Operation cancelled")
        return
    
    async with engine.begin() as conn:
        print("\n   Clearing data...")
        
        try:
            total_deleted = 0
            
            for table in table_names:
                result = await conn.execute(text(f"DELETE FROM {table}"))
                deleted = result.rowcount
                total_deleted += deleted
                print(f"      ✓ {table}: {deleted} records deleted")
            
            print(f"\n   ✓ Total records deleted: {total_deleted}")
            
        except Exception as e:
            print(f"\n   ✗ Error clearing data: {e}")
            return
    
    print("\n" + "=" * 60)
    print("✓ Data cleared successfully!")
    print("=" * 60)
    
    await engine.dispose()


async def clear_test_data():
    """Clear only test data (users with test emails)."""
    engine = get_engine()
    
    print("=" * 60)
    print("ARIA - Clear Test Data")
    print("=" * 60)
    print("\n   This will delete users with 'test' in their email and all related data.")
    
    # Ask for confirmation
    response = input("\n   Type 'yes' to confirm: ").strip().lower()
    
    if response != 'yes':
        print("\n   ✗ Operation cancelled")
        return
    
    async with engine.begin() as conn:
        print("\n   Finding test users...")
        
        try:
            # Find test users
            result = await conn.execute(
                text("SELECT id, email FROM users WHERE email LIKE '%test%'")
            )
            test_users = result.fetchall()
            
            if not test_users:
                print("      ℹ No test users found")
                return
            
            print(f"      Found {len(test_users)} test user(s):")
            for user in test_users:
                print(f"         - {user.email} (ID: {user.id})")
            
            print("\n   Deleting test users and related data...")
            
            # Delete test users (cascade will handle related data)
            for user in test_users:
                await conn.execute(
                    text("DELETE FROM users WHERE id = :user_id"),
                    {"user_id": user.id}
                )
            
            print(f"\n   ✓ Deleted {len(test_users)} test user(s) and all related data")
            
        except Exception as e:
            print(f"\n   ✗ Error clearing test data: {e}")
            return
    
    print("\n" + "=" * 60)
    print("✓ Test data cleared successfully!")
    print("=" * 60)
    
    await engine.dispose()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Clear data from ARIA database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/clear_data.py                    # Clear all data (with confirmation)
  python scripts/clear_data.py --test-only        # Clear only test users
  python scripts/clear_data.py --tables users     # Clear specific table(s)
        """
    )
    
    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Clear only test data (users with 'test' in email)"
    )
    
    parser.add_argument(
        "--tables",
        nargs="+",
        help="Clear specific tables only (space-separated)"
    )
    
    args = parser.parse_args()
    
    try:
        if args.test_only:
            asyncio.run(clear_test_data())
        elif args.tables:
            asyncio.run(clear_specific_tables(args.tables))
        else:
            asyncio.run(clear_all_data())
    
    except KeyboardInterrupt:
        print("\n\n   ✗ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
