# QWEEN AI Tools

A collection of intelligent creative tools built for the QWEEN team.

**V1 tool — Image Upscaler:** enhance and upscale jewellery imagery while
preserving fine detail, powered by the [fal.ai Crystal Upscaler](https://fal.ai/models/clarityai/crystal-upscaler).

This is an internal, local, one-command application. No accounts, database,
cloud storage, or deployment infrastructure — but the code is structured so more
QWEEN AI tools can be added later.

---

## Quick start

### 1. Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Node.js 18+** and npm

### 2. Install dependencies

From the repository root:

```bash
npm install
npm run setup
```

`npm run setup` creates the backend Python virtual environment
(`backend/.venv`), installs the Python requirements, and installs the frontend
npm packages.

> If you prefer to do it by hand:
> ```bash
> cd backend && python3.12 -m venv .venv && ./.venv/bin/pip install -r requirements.txt && cd ..
> cd frontend && npm install && cd ..
> ```

### 3. Create your `.env` and add your FAL_KEY

Copy the example file and add your fal.ai key:

```bash
cp .env.example backend/.env
```

Then edit `backend/.env` and set your key (format is `id:secret`):

```env
FAL_KEY=your-id:your-secret
```

The `FAL_KEY` lives **only** on the backend. It is never exposed to the
frontend, never returned in an API response, and never logged.

You can get a key from the [fal.ai dashboard](https://fal.ai/dashboard/keys).
Make sure the account has **billing / credits configured** — otherwise fal.ai
returns `401` during upload and the tool will tell you billing is not set up.

### 4. Start the application

```bash
npm run dev
```

This starts both the FastAPI backend (port `8000`) and the Vite frontend
(port `5173`) together.

### 5. Open the app

Open **http://localhost:5173** in your browser.

---

## Configuration (`backend/.env`)

| Variable                | Default | Description                                                        |
| ----------------------- | ------- | ------------------------------------------------------------------ |
| `FAL_KEY`               | —       | fal.ai credentials, `id:secret`. Backend only. **Required to run.**|
| `USD_TO_INR`            | `90`    | Approximate INR conversion for the displayed cost estimate.        |
| `MAX_CONCURRENCY`       | `4`     | Hard ceiling on concurrent images. The backend enforces this.      |
| `IMAGE_TIMEOUT_SECONDS` | `180`   | Per-image processing timeout.                                      |
| `MAX_FILE_SIZE_MB`      | `50`    | Maximum accepted upload size per image.                            |
| `RESULT_TTL_MINUTES`    | `60`    | How long results are kept on disk before automatic cleanup.        |
| `HOST` / `PORT`         | `127.0.0.1` / `8000` | Backend bind address.                                 |
| `CORS_ORIGINS`          | Vite dev URLs | Comma-separated list of allowed frontend origins.            |

> **Changing the backend port:** set `PORT` in `backend/.env` *and* run the dev
> command with a matching proxy target, e.g.
> `PORT=8010 VITE_BACKEND_URL=http://127.0.0.1:8010 npm run dev`.

---

## How it works

The workflow is built around an explicit **cost gate** — no paid fal.ai call
ever happens before you confirm:

```
Select images → Scan & Estimate → Show cost → Confirm & Run → Process → Before/After → Download
```

- **Scan & Estimate** validates each image with Pillow, reads real dimensions,
  and computes the authoritative cost (`$0.016 × output megapixels`). It never
  calls fal.ai.
- **Confirm & Run** is the only action that starts paid processing.
- Each image is processed independently with bounded concurrency and a
  per-image timeout, so one failure or timeout never stops the batch.
- Live progress streams over **Server-Sent Events**.
- Completed images get an interactive **before/after slider**, individual
  downloads, and a **Download All** ZIP. Failed / timed-out images can be
  retried without re-charging the successful ones.

---

## Optional: Supabase settings & prompts store

By default the app runs fully local with no database. You can optionally back
**system settings and prompt templates** with Supabase (no images, no job
history, no auth are stored there).

1. **Get your keys.** Supabase Dashboard → your project → **Project Settings →
   API Keys**. Copy the **`service_role`** (secret) key. The project URL is
   `https://icszdwcdpipuarsctqfo.supabase.co`.
2. **Create the tables.** In the Supabase **SQL Editor**, run
   [`supabase/schema.sql`](supabase/schema.sql).
3. **Configure the backend** (`backend/.env`):
   ```env
   SUPABASE_URL=https://icszdwcdpipuarsctqfo.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-secret
   ```
   The service key is **backend only** — never in the frontend or a commit.
4. Restart `npm run dev`. Editable defaults (scale, concurrency, suffix, INR
   rate) now come from Supabase, overlaid on env defaults.

If Supabase is not configured, everything still works on env defaults and the
settings endpoints report `configured: false`.

**Endpoints**

| Method & path                         | Purpose                                  |
| ------------------------------------- | ---------------------------------------- |
| `GET /api/settings`                   | Effective settings + whether editable    |
| `PUT /api/settings`                   | Update editable defaults (validated)     |
| `GET /api/settings/prompts?tool_id=`  | List prompt templates for a tool         |
| `PUT /api/settings/prompts`           | Create/update a prompt (`name`, `prompt`)|
| `DELETE /api/settings/prompts?name=`  | Delete a prompt                          |

Example:

```bash
curl -X PUT http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"default_scale_factor": 4, "usd_to_inr": 85}'
```

---

## Project structure

```
qween-ai-tools/
├── package.json            # one-command dev orchestration (concurrently)
├── .env.example
├── README.md
│
├── backend/                # FastAPI application
│   ├── requirements.txt
│   └── app/
│       ├── main.py         # app entry, tool registry, CORS, cleanup
│       ├── config.py       # env-driven settings (holds FAL_KEY)
│       ├── core/logging.py # secret-safe logging
│       ├── tools/
│       │   └── upscaler/   # the Image Upscaler tool
│       │       ├── router.py       # HTTP API
│       │       ├── service.py      # scan / estimate
│       │       ├── cost.py         # authoritative cost calc
│       │       ├── validation.py   # Pillow image validation
│       │       ├── filenames.py    # safe upload / output names
│       │       └── models.py
│       ├── providers/
│       │   ├── fal/        # fal.ai upload + Crystal Upscaler + error mapping
│       │   └── supabase/   # optional settings/prompts store (PostgREST)
│       ├── settings/       # system settings service + API (env + Supabase)
│       ├── jobs/           # in-memory job state, SSE bus, worker pool
│       └── storage/        # local temp storage + TTL cleanup
│
└── frontend/               # React + Vite + TypeScript
    └── src/
        ├── App.tsx
        ├── components/     # AppShell, BeforeAfterSlider
        ├── lib/            # api client, types, formatting, image helpers
        └── tools/upscaler/ # the tool UI (state machine, views)
```

The separation is deliberate: **Tool → Provider → Job → Storage**. A future
tool (AI Look Studio, Background Generator, …) adds its own
`tools/<name>/router.py` and registers it in `main.py` without touching the
upscaler.

---

## Tests

```bash
npm run test          # backend unit + API + worker tests
npm run build         # type-check + build the frontend
```

The backend suite covers cost math, image validation, filename safety, the scan
API, the cost gate, and batch behaviour (failure isolation, timeout, retry)
using a test-only provider double. The real fal.ai integration is never mocked
in the running application.

---

## Notes & limitations (V1)

- **In-memory state, local temp storage.** Job state and results live in the
  backend process and under your system temp dir (`.../qween-ai-tools/`). They
  are cleaned up after `RESULT_TTL_MINUTES`; restarting the backend clears
  everything. This is intentional for V1 — no database.
- **Supported inputs:** `.jpg`, `.jpeg`, `.png`, `.webp` only. No folders, RAW,
  TIFF, PDF, or video.
- **A funded fal.ai account is required** to actually upscale. Without credits,
  fal.ai returns `401` on upload and the tool surfaces a clear
  "billing / credits are not configured" message.
- Optimised previews are shown in the UI; the full-resolution output is always
  what you download.
```
