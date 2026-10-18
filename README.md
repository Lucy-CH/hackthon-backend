# Hong Kong Rent & Commute — Backend

FastAPI backend for searching Hong Kong work addresses and recommending rental homes by budget and public transport commute. Recommendations include route geometry and travel steps, estimated monthly transport costs, and estimated carbon emissions.

Built with Python, uv, FastAPI, SQLAlchemy, Alembic, PostgreSQL, and Google Routes API.

## Requirements

- **uv**: install it using the [official instructions](https://docs.astral.sh/uv/getting-started/installation/).
- **Python 3.12**: uv can install it as shown below.
- **Docker with Docker Compose**: Docker Desktop on macOS/Windows, or Docker Engine with the Compose plugin on Linux. Docker must be running.
- Your own server-side Google API key with **Routes API** enabled and an active billing account, to calculate recommendations.

For local development, PostgreSQL runs in Docker and FastAPI runs on your computer through uv. The frontend runs separately with Node.js. You do not need to install PostgreSQL directly on your computer.

## First-time local setup

Run commands from the backend repository directory, which contains `pyproject.toml` and `compose.yaml`.

### 1. Install Python and dependencies

```bash
uv python install 3.12
uv sync --locked
```

The project uses `.python-version` to select Python 3.12. `uv.lock` pins dependency versions. There is no need to activate `.venv` manually when using `uv run`.

### 2. Configure environment variables

On macOS/Linux:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

If `.env` already exists, edit it instead of overwriting it. The template contains:

```dotenv
ENVIRONMENT=development
WEB_APP_NAME="Hackthon Backend Api"
WEB_CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"

DB_HOST=127.0.0.1
DB_PORT=15432
DB_NAME=hackthon
DB_USER=hackthon
DB_PASSWORD=change_me_for_local_development

GOOGLE_ROUTES_API_KEY=replace_with_your_google_routes_api_key
```

Set your own local database password before initializing PostgreSQL, and replace the Google Routes key placeholder to use recommendations.

| Variable | Purpose |
| --- | --- |
| `WEB_APP_NAME` | Application title in API documentation. |
| `WEB_CORS_ORIGINS` | Comma-separated frontend origins allowed to call the API. Include the actual frontend port. |
| `DB_HOST` | `127.0.0.1` when FastAPI runs on your computer. |
| `DB_PORT` | Host port published by local Compose; the example uses `15432`. PostgreSQL inside Docker uses `5432`. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Database initialization values and application connection credentials. |
| `GOOGLE_ROUTES_API_KEY` | Server-side Routes API key; keep it separate from the frontend browser Maps key. |

The settings module loads the Routes key at import time, including for migration/import commands. Keep this variable present even when only setting up the database. Those commands do not call Google, but recommendations need a valid key.

Real `.env` and `.env.prod` files are ignored by Git. Do not put real credentials in `.env.example`.

### 3. Start PostgreSQL

```bash
docker compose up -d postgres
docker compose ps
```

Wait until PostgreSQL shows `healthy`. If it is already running, check its status and continue.

For troubleshooting:

```bash
docker compose logs --tail=50 postgres
```

PostgreSQL data is stored in a Docker volume. Initialization credentials are applied only when the volume is first created; editing `.env` does not change an existing database user's password or rename an existing database.

### 4. Create the tables

```bash
uv run alembic upgrade head
```

This applies the migration files committed in `migrations/versions/`. Do not generate new migrations just to initialize a fresh checkout.

### 5. Import the supplied datasets

Confirm these files are present:

```text
data/
├── ALS-GeoJSON.zip
└── rentals/
    └── 28hse_rentals.csv
```

These files are explicitly allowed by `.gitignore` and must be included in the checkout or release package. Other files under `data/`, including database backups, remain ignored. If either file is missing, obtain it from the project maintainer before continuing.

Optionally preview the data without writing to the database:

```bash
uv run python -m app.scripts.import_addresses --dry-run
uv run python -m app.scripts.import_rentals --dry-run
```

Then import it:

```bash
uv run python -m app.scripts.import_addresses
uv run python -m app.scripts.import_rentals
```

- The address importer skips unusable coordinates and duplicate address records.
- The rental importer skips missing/invalid coordinates and existing listing IDs. The current CSV has 73 records, with 43 coordinate-valid records in the initial import.
- Re-running these scripts skips existing matching records; it does not refresh or overwrite those records.
- For another input file, both scripts accept `--file PATH`.

These are real address data and historical rental snapshots, not fictional fixtures or live availability. The filenames identify the ALS and 28Hse datasets. Before redistributing them beyond the project, verify the upstream reuse terms and retain applicable attribution. The repository does not establish a separate license for third-party data.

### 6. Start the API

```bash
uv run fastapi dev app/main.py
```

If `make` is installed, the equivalent shortcut is:

```bash
make dev
```

Open:

- API documentation: **http://127.0.0.1:8000/docs**
- OpenAPI schema: **http://127.0.0.1:8000/openapi.json**

Keep this terminal running. This is a development server with automatic reload. For the frontend, set `VITE_API_BASE_URL=http://127.0.0.1:8000` and start it separately.

## Test the API

### Address search

```bash
curl --fail-with-body --get \
  'http://127.0.0.1:8000/api/code-tables/address_list' \
  --data-urlencode 'q=Central' \
  --data-urlencode 'limit=2'
```

Successful responses wrap results in `data`; address results are under `data.items`.

### Rental recommendations

In `/docs`, open **POST /api/recommendations** and click **Try it out**. Use an address ID returned by your own address search, and a rent budget:

```json
{
  "work_address_id": 1,
  "max_monthly_rent_hkd": 12000
}
```

`1` is only an example: replace it with a valid ID from your database. IDs need not match another developer's database. This request calls Google Routes API and may incur usage charges. An empty result can mean no homes meet the budget or no transit routes were returned.

## Everyday development

For an existing installation:

```bash
docker compose up -d postgres
uv sync --locked
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

Initial data imports normally only need to run once per database.

| Make command | Equivalent / purpose |
| --- | --- |
| `make dev` | `uv run fastapi dev app/main.py` |
| `make db-upgrade` | `uv run alembic upgrade head` |
| `make db-migrate` | Generate an Alembic migration from model changes; review the generated file before applying and committing it. |
| `make db-downgrade` | Roll back one migration; inspect its downgrade first because it may remove data. |

When changing SQLAlchemy models, commit the model changes and reviewed migration together. Teammates pull the code and run `alembic upgrade head`. Changing a model alone does not update an existing database.

To stop local PostgreSQL while retaining its data:

```bash
docker compose stop postgres
```

Do not use `docker compose down -v` unless you intentionally want to delete the local database volume and all its data.

## Local development versus server deployment

| File | Purpose |
| --- | --- |
| `compose.yaml` | Local PostgreSQL only; API runs through uv on the host. |
| `.env.example` | Safe example configuration to copy into `.env`. |
| `Dockerfile` | Builds the API image for server deployment. |
| `.dockerignore` | Excludes local credentials, virtual environments, and datasets from the image build. |
| `compose.prod.yaml` | Server services: API, PostgreSQL, and Caddy. |
| `Caddyfile` | Serves frontend files and forwards `/api/*` to the API. |

The server Compose file expects a private `.env.prod` and prebuilt frontend files at `../frontend/dist` relative to its directory. It is not the local first-time setup command. In the API container, Compose sets `DB_HOST=postgres` and `DB_PORT=5432` for internal networking.

The backend image does not include the datasets and does not automatically run migrations or imports. A new server needs an explicit database initialization or backup restore before use. After restoring a complete database backup, check its Alembic version before applying any newer migrations.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Docker connection error | Docker Desktop or Docker Engine is running. |
| `Connection refused` | PostgreSQL is healthy and `.env` uses the published host port, normally `15432` here. |
| Password authentication fails | `.env` credentials match the existing database volume, not just newly edited initialization values. |
| Missing table / relation does not exist | Run `uv run alembic upgrade head` against the intended database. |
| Searches return no data | Run the address and rental import scripts after creating the tables. |
| Import file not found | Confirm both dataset files exist at the documented paths, or pass `--file`. |
| Missing settings validation error | Create `.env` and include all required database fields and `GOOGLE_ROUTES_API_KEY`. |
| Browser reports CORS errors | Add the actual frontend origin to `WEB_CORS_ORIGINS` and restart the API. |
| Recommendations fail | Check backend logs, Routes API enablement, key restrictions, billing, and quota. |
| `make` is unavailable | Run the equivalent `uv run ...` command directly. |

## Prototype assumptions

- Rental data is historical; availability is not verified.
- Arrival time defaults to 9:30 AM on the next weekday selected by the backend; public holidays are not handled separately.
- Monthly transport cost assumes 22 commuting days, two trips per day, and equal fares in both directions. Missing/non-HKD fares yield unavailable cost estimates.
- Carbon estimates use UK 2026 transport factors as proxies for Hong Kong, including an urban-rail approximation. They are not measured route emissions.
- Monthly emissions assume the same route in both directions. Unsupported transport modes or missing segment distances yield unavailable emissions estimates.
- Recommendations choose the shortest-duration route among those returned for each rental and are initially sorted by commute duration.

## DeepSeek AI rental picks

`POST /api/recommendations` now also returns `data.ai`, while preserving the
complete `data.items` list and its original commute ordering. AI runs after rent
filtering and route calculation, within the same HTTP request (not streaming).
Only rentals with a returned transit route are eligible. No migration is needed.

Configure the backend `.env` (or `.env.prod` for production Compose):

```dotenv
DEEPSEEK_API_KEY=your_server_side_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_TIMEOUT_SECONDS=20
DEEPSEEK_MAX_CANDIDATES=50
```

Restart the backend after configuration. Keep the key on the server; never put it
in frontend `VITE_*` variables. The implementation uses DeepSeek's
[JSON Output API](https://api-docs.deepseek.com/guides/json_mode/) through the existing
httpx dependency with thinking mode disabled for concise, low-latency picks. Model and base URL can be overridden for your DeepSeek account.

Example request (replace the work address ID with a real database ID):

```json
{
  "work_address_id": 1,
  "max_monthly_rent_hkd": 12000,
  "include_ai": true,
  "ai_recommendation_count": 2,
  "preferences": "希望少换乘，步行少一些，优先节省租金"
}
```

`include_ai` defaults to `true`; set it to `false` to skip the external AI call.
`ai_recommendation_count` accepts 1 or 2 (default 2). A single eligible listing
produces one pick. Preferences are optional and limited to 1,000 characters.
The budget is **rent only**, not rent plus transport.

Example `data.ai` (illustrative IDs and text):

```json
{
  "status": "success",
  "recommendations": [
    {"rental_id": 17, "reason": "租金较低且通勤换乘少，符合节省租金的偏好。", "tradeoff": "交通费未知，需要另行确认。"},
    {"rental_id": 23, "reason": "通勤时间较短，适合优先考虑出行便利。", "tradeoff": "租金相对更高。"}
  ],
  "considered_count": 18,
  "message": null
}
```

Frontend integration: match each `recommendations[].rental_id` to `data.items`,
then display the property together with `reason` and `tradeoff` in that order.
Render these strings as text, never raw HTML. This backend branch does not change
the frontend; existing clients continue to display their original listing list.

| `data.ai.status` | Meaning |
| --- | --- |
| `success` | Validated AI picks, in recommendation order. |
| `disabled` | Request has `include_ai: false`. |
| `not_configured` | Server key is empty; original search still succeeds. |
| `no_candidates` | No budget-qualified listings with transit routes. |
| `unavailable` | Upstream timeout/error or invalid AI output; original search still succeeds. |

Failures expose no provider response bodies or secrets. Returned IDs must be
unique members of the server-selected candidate set and match the requested
count. Reasons are model-generated and should be checked against listing data.
No deterministic fallback is presented as an AI recommendation.

To bound latency/context, AI considers at most `DEEPSEEK_MAX_CANDIDATES` listings
(default 50), alternating fastest-commute and cheapest-rent choices before
removing duplicates. `considered_count` reports the actual number supplied to AI;
`data.items` remains complete. Picks are best matches among that shortlist, not a
guarantee of the globally best rental. The request adds up to the configured AI
deadline after route calculation. There are no automatic retries.

DeepSeek receives the optional preferences and a compact subset of historical
listing data (ID, district, rent, commute metrics, cost/emissions estimates and
fetch date). Exact addresses, coordinates, listing URLs, route geometry and the
work destination are not sent. Missing estimates remain unknown, not zero.

Run the isolated tests without a database or paid API calls:

```bash
uv run python -m unittest discover -s tests -v
```

### Side-by-side comparison and overall recommendation

Search responses now include `data.comparison` when AI is enabled. The backend
compares up to three homes: the AI picks followed by the cheapest remaining
alternatives. With fewer than two routed homes, no comparison AI call is made.
This adds a second DeepSeek call after the initial picks; each call has its own
configured deadline. If comparison AI fails, the factual table still returns.

`POST /api/recommendations/compare` accepts the search fields plus `rental_ids`
(2–3 distinct IDs). It revalidates IDs against database rent/coordinate filters
and recalculates routes for those homes only. It does not accept client-provided
listing metrics. If any selected home has no route, it returns 422 and asks the
client to search again. No search cache or browser-supplied metrics are trusted.

```json
{
  "work_address_id": 1,
  "max_monthly_rent_hkd": 12000,
  "preferences": "希望少换乘，优先节省租金",
  "include_ai": true,
  "rental_ids": [17, 23, 28]
}
```

The response contains `items`, `differences`, `status`, and optional `narrative`.
Differences are each home minus the first home, computed by backend code.
Missing inputs produce null differences; emissions with different factor
versions are not compared. Rent, transit costs and total cost remain distinct.
`narrative` includes one recommended ID, an overall conclusion and strengths,
tradeoffs and suitable audience for every compared home. ID coverage is validated.
Comparison AI explanations are in English regardless of the preference language
and use qualitative tradeoffs; factual values/differences are rendered
from backend data. Free-text explanations still require human fact checking.

### Rich property details

Apply the new migration and backfill optional CSV attributes for existing rows:

```bash
uv run alembic upgrade head
uv run python -m app.scripts.import_rentals --update-details
```

The explicit backfill updates only `property_details` on matching listing IDs;
it preserves existing rents, coordinates and snapshot dates. Default imports
still skip existing IDs. New imports include the optional details automatically.
The allowlist preserves property type, bathrooms, floor, kitchen type, building
age, estate, description, rent inclusions, subletting, cooking and sharing terms.
Bedrooms and saleable area use the existing database fields. Missing values
remain unknown; listing descriptions are unverified claims.

- `GET /api/recommendations/{rental_id}` returns property facts without a Routes
  or DeepSeek call. Missing IDs return 404.
- `POST /api/recommendations/{rental_id}/analysis` takes the usual search request,
  revalidates rent, recalculates that home's route, and returns an English
  assessment of strengths, tradeoffs, suitability and overall fit. The full
  facts remain accessible if route/AI services fail.
- Search no longer generates a comparison automatically. It returns compact AI
  picks; comparison and detailed assessment are requested from the detail page.
  This supersedes the earlier automatic-comparison description above.

Both recommendation and comparison AI now receive bedrooms, saleable area and
allowlisted optional property data. Narrative output is English. Descriptions
are length-bounded and treated as untrusted, unverified source claims.
