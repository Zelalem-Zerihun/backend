import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres:1234@localhost:5432/accos_db")
    result = await conn.execute(
        "UPDATE users SET role = 'admin' WHERE email = $1",
        "zelalem.zerihun.b@gmail.com"
    )
    row = await conn.fetchrow(
        "SELECT email, role FROM users WHERE email = $1",
        "zelalem.zerihun.b@gmail.com"
    )
    print("Result:", result)
    print("User now:", row["email"], "->", row["role"])
    await conn.close()

asyncio.run(main())
