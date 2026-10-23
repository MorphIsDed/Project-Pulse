# ProjectPulse

Local project planning and analytics application. Initial stack: React + TypeScript frontend, Flask API, and SQLite.

## Start the API

From `backend`, install the package with `python -m pip install -e .`, then run `flask --app wsgi run --debug`. The health endpoint is `http://127.0.0.1:5000/api/v1/health`. Initialize the SQLite database with `flask --app wsgi init-db`.

## Start the frontend

From `frontend`, run `npm install` once and `npm run dev`. Vite proxies `/api` requests to the Flask development server at port 5000.

