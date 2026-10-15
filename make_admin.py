import asyncio
import asyncpg
from app.core.config import settings

async def main():
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    email = "zelalem.zerihun.b@gmail.com"
    result = await conn.execute(
        "UPDATE users SET role = 'admin' WHERE email = $1",
        email
    )
    row = await conn.fetchrow(
        "SELECT email, role FROM users WHERE email = $1",
        email
    )
    print("Result:", result)
    if row:
        print("User now:", row["email"], "->", row["role"])
    else:
        print(f"Note: User '{email}' does not exist yet. Register through the app first, then run this script to grant admin role.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())

