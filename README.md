# Medical Store Management System

## Local setup

1. Install MySQL and create the app-only database and user. The app should use a database name and MySQL account separate from any other project.
2. Copy `.env.example` to `.env` and enter the database password. Keep `.env` private; it is ignored by Git.
3. Install packages into the project virtual environment:

   ```powershell
   .\venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Create or upgrade the tables in the already-created database:

   ```powershell
   .\venv\Scripts\python.exe database.py
   ```

5. Start the app:

   ```powershell
   .\venv\Scripts\python.exe app.py
   ```

6. Open `http://127.0.0.1:5000`. The first setup creates `admin` with password `admin123`; the app requires changing it at first login.

The application stores password hashes, uses a session secret from `.env`, checks CSRF tokens on POST forms, uses transactions for sales/stock updates, and records invoice line details so past invoices remain readable if a medicine is later changed or deleted.

## Database isolation

The app connects only to the database configured by `DB_NAME`. `database.py` creates tables inside that database; it does not create databases or grant MySQL privileges. Use an app-specific account that has privileges only on the medical-store database.
