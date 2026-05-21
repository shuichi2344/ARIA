"""
Reset database by dropping all tables and re-running migration.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aria.database.connection import get_engine
from sqlalchemy import text


async def reset_database():
    """Drop all tables and re-run migration."""
    engine = get_engine()
    
    print("=" * 60)
    print("ARIA - Database Reset")
    print("=" * 60)
    
    # Read migration file
    migration_file = Path(__file__).parent.parent / "migrations" / "001_initial_schema.sql"
    
    if not migration_file.exists():
        print(f"✗ Migration file not found: {migration_file}")
        return
    
    migration_sql = migration_file.read_text()
    
    async with engine.begin() as conn:
        print("\n1. Dropping all tables...")
        try:
            # Drop tables in reverse order of dependencies
            await conn.execute(text("DROP TABLE IF EXISTS market_impact_reports CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS simulation_analysis CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS agent_interactions CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS simulation_events CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS simulations CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS scenarios CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS archetypes CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS business_profiles CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS error_logs CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
            print("   ✓ All tables dropped")
        except Exception as e:
            print(f"   ✗ Error dropping tables: {e}")
            return
        
        print("\n2. Running migration...")
        try:
            # Split migration into individual statements
            statements = [s.strip() for s in migration_sql.split(';') if s.strip()]
            
            for i, statement in enumerate(statements, 1):
                if statement:
                    await conn.execute(text(statement))
            
            print(f"   ✓ Migration completed ({len(statements)} statements)")
        except Exception as e:
            print(f"   ✗ Migration failed: {e}")
            return
    
    print("\n" + "=" * 60)
    print("✓ Database reset completed!")
    print("=" * 60)
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset_database())
