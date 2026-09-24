   🐘 PostgreSQL Setup Guide for AccOS Backend

  This guide walks you through installing PostgreSQL on Windows, creating the project database, and running your first Alembic migration.
  ──────
  ## 1. Install PostgreSQL

  ### Option A — Official Installer (Recommended)

  1. Download the latest PostgreSQL 16+ Windows installer from:
  https://www.postgresql.org/download/windows/
  2. Run the installer. During setup:
      • Set a superuser password for the postgres user (remember this!).
      • Keep the default port 5432.
      • When prompted for components, include pgAdmin 4 (graphical management tool) and Command Line Tools.
  3. After installation, make sure the PostgreSQL bin directory is on your PATH:
    # Typically something like:
    $env:PATH += ";C:\Program Files\PostgreSQL\16\bin"
    # To make it permanent, add it via System Environment Variables

  4. Verify installation:
    psql --version
    # Expected: psql (PostgreSQL) 16.x


  ### Option B — Using Chocolatey

    choco install postgresql --params "/Password:postgres /Port:5432"

  ### Option C — Using Docker (If you prefer containers)

    docker run -d `
      --name accos-postgres `
      -e POSTGRES_USER=postgres `
      -e POSTGRES_PASSWORD=postgres `
      -e POSTGRES_DB=accos_db `
      -p 5432:5432 `
      postgres:16-alpine

  │ If you use Docker, skip Step 2 below — the database is already created.
  ──────
  ## 2. Create the Database

  Open a terminal and connect to PostgreSQL as the superuser:

    psql -U postgres

  Enter your superuser password when prompted, then run:
  -- Create the project database
    CREATE DATABASE accos_db;

    -- (Optional) Create a dedicated user instead of using postgres
    CREATE USER accos_user WITH PASSWORD 'your_secure_password';
    GRANT ALL PRIVILEGES ON DATABASE accos_db TO accos_user;

    -- If using PostgreSQL 15+, also grant schema permissions
    \c accos_db
    GRANT ALL ON SCHEMA public TO accos_user;

    -- Exit psql
    \q

  │ Note: If you create a dedicated user, update your .env file accordingly:
  │
  │   DATABASE_URL=postgresql+asyncpg://accos_user:your_secure_password@localhost:5432/accos_db
  ──────
  ## 3. Verify Connectivity

  Test that the application can reach your database:

    cd C:\Users\hp\Desktop\AccOS\backend

    .\.venv\Scripts\python.exe -c "
    import asyncio
    from app.core.database import engine

    async def check():
        async with engine.connect() as conn:
            result = await conn.execute(__import__('sqlalchemy').text('SELECT version()'))
            print(f'Connected! {result.scalar()}')

    asyncio.run(check())
    "

  You should see output like:

    Connected! PostgreSQL 16.x on ...
  ──────
    ## 4. Run the Initial Migration

  Once the database is accessible, generate and apply the initial schema:

    cd C:\Users\hp\Desktop\AccOS\backend

    # Generate the migration file (autogenerate diffs models vs. empty DB)
    .\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "initial_schema"

    # Apply the migration (creates all 8 tables)
    .\.venv\Scripts\python.exe -m alembic upgrade head

  ### Verify the tables were created

    psql -U postgres -d accos_db -c "\dt"

  You should see all 8 tables:

     Schema |       Name         | Type  | Owner
    --------+--------------------+-------+----------
     public | ai_rate_limits     | table | postgres
     public | alembic_version    | table | postgres
     public | modules            | table | postgres
     public | subscriptions      | table | postgres
     public | topic_attachments  | table | postgres
     public | topic_contents     | table | postgres
     public | topics             | table | postgres
     public | user_progress      | table | postgres
     public | users              | table | postgres
  ──────
  ## 5. Start the Application

    cd C:\Users\hp\Desktop\AccOS\backend


  Open http://localhost:8000 → should return:

    {"status": "healthy", "app": "AccOS E-Learning API", "version": "0.1.0"}

  Open http://localhost:8000/docs for the interactive Swagger UI.
  ──────
  ## Quick Reference: Key .env Variables

   Variable                                                    | Default                                                        | Description
  -------------------------------------------------------------|----------------------------------------------------------------|-------------------------------------------------------------
   DATABASE_URL                                                | postgresql+asyncpg://postgres:postgres@localhost:5432/accos_db | Full async connection string
   SECRET_KEY                                                  | change-me-...                                                  | Must be changed for production
   DEBUG                                                       | true                                                           | Enables SQL echo logging
     ## Troubleshooting

   Problem                                                                                    | Solution
  --------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------
   psql: connection refused                                                                   | PostgreSQL service isn't running. Start it: net start postgresql-x64-16 (or via Services app)
   FATAL: password authentication failed                                                      | Double-check the password in .env matches what you set during PG install
   FATAL: database "accos_db" does not exist                                                  | You skipped Step 2. Run CREATE DATABASE accos_db; in psql
   connection refused on port 5432                                                            | Check PG is listening: netstat -an | findstr 5432
   Alembic Target database is not up to date                                                  | Run ..venv\Scripts\python.exe -m alembic upgrade head first