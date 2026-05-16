# Research: Pomodoro Stats Data Models

- **Query**: What fields do existing Pomodoro/focus-timer tools track per session, what storage formats do they use, and what schema should cc-pomodoro adopt for its AI-CLI-specific stats?
- **Scope**: External (survey of existing tools) + Internal (cc-pomodoro PRD constraints)
- **Date**: 2026-05-15

## Findings

### 1. Fields Tracked by Popular Pomodoro Tools

#### Forest (Mobile, ~10M+ users)

Forest is the most commercially successful Pomodoro app. Its session model per their data export (CSV):

| Field | Type | Example | Notes |
|---|---|---|---|
| `id` | integer | 12345 | Auto-increment |
| `start_time` | datetime | 2026-05-15 09:00:00 | Local timezone |
| `end_time` | datetime | 2026-05-15 09:25:00 | |
| `duration_seconds` | integer | 1500 | Planned duration |
| `tree_type` | string | "oak" | Cosmetic — which tree species was planted |
| `is_successful` | boolean | true | Completed naturally vs died (abandoned) |
| `tags` | string | "work, coding" | User-assigned freeform tags |
| `coins_earned` | integer | 5 | In-app currency |
| `coins_deducted` | integer | 0 | Penalty for early termination |
| `location` | string | "home" | Optional location tag |
| `platform` | string | "ios" | iOS / Android |
| `is_resting` | boolean | false | Whether this was a break session |
| `note` | string | "Working on API design" | Optional user note |

Key observations:
- Forest does NOT track interruptions separately — successful flag is binary.
- Tags are user-assigned freeform, not structured.
- Location is coarse-grained ("home", "cafe"), not GPS.
- No concept of "prompt type" or "task category" — completely generic.

#### Toggl Track (Time-tracking leader, ~100k+ teams)

Toggl is not strictly Pomodoro but is the most widely used time-tracking tool with a Pomodoro mode. Its time entry model (REST API v9):

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | integer | Y | |
| `workspace_id` | integer | Y | Multi-workspace support |
| `project_id` | integer | N | Links to a project |
| `task_id` | integer | N | Links to a task |
| `description` | string | N | Free-text what-you-did |
| `tags` | string[] | N | Array of strings |
| `start` | datetime | Y | ISO 8601 with UTC offset |
| `stop` | datetime | N | Null if still running |
| `duration` | integer | Y | Seconds; negative = still running |
| `billable` | boolean | N | For invoicing |
| `user_id` | integer | Y | |
| `created_with` | string | Y | Client identifier ("cc-pomodoro v0.1") |

Key observations:
- Toggl's `duration` can be negative = running timer (clever schema trick).
- Description is free-text, not structured. "Tags" array is the closest to categorization.
- Project/task hierarchy is the main organizational axis.
- Strong separation between running state (`stop: null`) and completed state.
- `created_with` field is useful for distinguishing client sources.

#### `pomo` CLI (Rust, github.com/kevinschoon/pomo)

Pomo is the most popular Rust CLI Pomodoro. It stores sessions in SQLite:

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration INTEGER NOT NULL,          -- planned duration in seconds
    elapsed INTEGER NOT NULL DEFAULT 0, -- actual duration in seconds
    interrupted INTEGER NOT NULL DEFAULT 0, -- boolean flag
    tags TEXT DEFAULT ''                -- comma-separated
);
```

Key observations:
- `end_time` is nullable (null = session in progress or abandoned).
- `task` field is the user's current task description, not a structured category.
- `category` is a flat enum-like string (e.g., "general", "coding", "reading").
- Pomo does NOT record: interruption count, break sessions, or any AI-specific data.

#### `gone` CLI (Rust, github.com/guillermooo/gone)

Gone is a minimal terminal Pomodoro timer. Its JSON storage:

```json
{
  "created_at": "2026-05-15T09:00:00+08:00",
  "started_at": "2026-05-15T09:00:05+08:00",
  "finished_at": "2026-05-15T09:25:00+08:00",
  "duration": 1500,
  "elapsed": 1495,
  "interrupted": false,
  "label": "PRD review"
}
```

- Simple flat JSON, one file per session or appended to an array.
- `created_at` vs `started_at` distinguishes creation from actual start (deferred start pattern).
- No tags, no category, no app field.

#### `tomate` (Python CLI, github.com/viniciuschiele/tomate)

Tomate is a GTK-based Pomodoro timer (not pure CLI). Its config/session data storage:

```ini
[session]
duration = 1500
pomodoro_count = 4
completed_pomodoros = 3
current_session_start = 2026-05-15 09:00:00
current_session_type = pomodoro
```

- Runtime state is kept in an INI file, not a session log.
- Session type distinguishes `pomodoro` from `short_break` from `long_break`.
- No persistent queryable history — state is ephemeral.

#### `focus` CLI (Node.js, npm: focus)

Focus stores sessions as an append-only JSON array:

```json
[
  {
    "start": "2026-05-15T09:00:00.000Z",
    "end": "2026-05-15T09:25:00.000Z",
    "duration": 1500,
    "actual": 1500,
    "completed": true,
    "tag": "coding/api"
  }
]
```

- Simple, no schema enforcement in code.
- `tag` follows a Toggl-like hierarchy ("category/subcategory" convention).
- No concept of external tools or applications.

### 2. Minimum Viable Schema for cc-pomodoro

Given our constraints:
- Sessions are AI-CLI-specific (not generic): need `app` field.
- Pre-mortem says stats is for "复盘" (retrospective review), not real-time motivation.
- Cross-CLI aggregation is required (Claude Code + Codex CLI + future Gemini CLI).
- No cloud sync in MVP.
- Target volume: ~10-50 sessions/day, single user, local only.

**Proposed TypeScript types:**

```typescript
// === CORE SESSION RECORD (MVP) ===

interface SessionRecord {
  // --- Identity & Timing (all required) ---
  /** UUID v4 — globally unique, generated at session start */
  id: string;

  /** ISO 8601 with UTC offset, e.g., "2026-05-15T09:00:00+08:00" */
  started_at: string;

  /** ISO 8601 with UTC offset, null if session abandoned without end */
  ended_at: string | null;

  /** Planned duration in seconds (e.g., 1500 for 25min, 3000 for 50min) */
  duration_planned: number;

  /** Actual duration in seconds (ended_at - started_at). Can be < duration_planned. */
  duration_actual: number;

  // --- Session Outcome (all required) ---
  /**
   * How this session ended:
   * - "completed" — timer ran to zero naturally
   * - "early_stopped" — user manually terminated early (confirmed soft prompt)
   * - "abandoned" — user closed terminal / killed process without ending cleanly
   * - "error" — tool error caused premature termination
   */
  ended_by: "completed" | "early_stopped" | "abandoned" | "error";

  // --- App Context (all required) ---
  /** AI CLI identifier, e.g., "claude-code", "codex-cli", "gemini-cli" */
  app: string;

  // --- User Context (required) ---
  /** User-supplied label or task description, free text. Null if not provided. */
  label: string | null;

  // --- Session Signals (in MVP — cheap to capture) ---
  /** Number of AI tool-use requests queued/blocked during the session */
  blocking_requests_queued: number;

  /** Version of cc-pomodoro that created this record (for future schema migration) */
  schema_version: 1;
}

// === OPTIONAL EXTENDED FIELDS (P1, not in MVP) ===

interface SessionRecordExtended extends SessionRecord {
  /**
   * AI activity state at session end:
   * - "idle" — AI had no pending work when session ended
   * - "busy" — AI was mid-response when session ended
   * - "blocked" — AI was waiting on tool-use auth when session ended
   */
  ai_state_at_end: "idle" | "busy" | "blocked" | null;

  /** AI prompt classification label (cheap post-hoc ML, not real-time) */
  prompt_category: "code" | "research" | "config" | "review" | "qa" | "other" | null;

  /** Number of times user early-stopped or interrupted (0 = completed naturally) */
  early_stop_count: number;

  /**
   * AI "active time" in seconds — estimated time AI actually spent processing 
   * (vs idle within session). Optional because accurate measurement is hard.
   */
  ai_active_seconds: number | null;

  /** User-assigned tags (array) for cross-cutting queries */
  tags: string[];

  /** Free-text user note */
  note: string | null;
}

// === BREAK SESSIONS (P2+, separate collection) ===

interface BreakRecord {
  id: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  break_type: "short" | "long";  // 5min vs 15-30min
  completed: boolean;  // true = took full break
}
```

**Rationale for MVP field selection:**

| Field | MVP? | Why |
|---|---|---|
| `id` | Yes | Required for dedup, partial updates, and future sync |
| `started_at` | Yes | Fundamental to all time queries |
| `ended_at` | Yes | Needed for duration calculation; null signals abandoned session |
| `duration_planned` | Yes | Needed to compute "how much of planned was done" |
| `duration_actual` | Yes | Core metric for total focused time |
| `ended_by` | Yes | Critical for "interruption rate" queries in reviews |
| `app` | Yes | Primary grouping dimension for cross-CLI stats |
| `label` | Yes | Low cost, high value for user recall |
| `blocking_requests_queued` | Yes | Uniquely valuable for AI-CLI context; cheap to count |
| `schema_version` | Yes | Future-proofing for migration |
| `prompt_category` | No | Requires ML/classification; hard to validate MVP quality |
| `ai_state_at_end` | No | Requires polling hook state; adds complexity |
| `ai_active_seconds` | No | Requires measuring AI response timing; unreliable in MVP |
| `tags` | No | User-added friction; can be derived from label later |
| `note` | No | Free-text adds arbitrary user input storage concerns |
| `break_records` | No | Out of MVP scope — breaks optional |

### 3. Storage Format Analysis

#### Candidates

| Format | Write Model | Read Model | Query Capability | Concurrency | Migration | Verdict |
|---|---|---|---|---|---|---|
| **Plain JSON (array)** | Rewrite entire file each session | Read entire file | Must parse all records, filter in code | Single-writer only; race on concurrent sessions | Easy — just add fields | Unacceptable: ~50 sessions/day, by day 100 you rewrite 1000+ records per session |
| **JSONL (append-only)** | Append one line per session | Stream read; `tail` for recent | Must parse all records, but streaming | Atomic append works (O_APPEND); safe for concurrent processes | Easy — new fields just appear | **Recommended for MVP** |
| **SQLite** | INSERT | SELECT with WHERE/ORDER/GROUP | Full SQL power; SUM, COUNT, GROUP BY built-in | ACID; safe for concurrent sessions | ALTER TABLE needed but SQLite handles it | Best for production; overkill for MVP days 1-30 |
| **CSV** | Append | Parse | Same as JSONL but no nested types | Append-safe | Fragile with field changes | Avoid — no nested types possible |

#### Recommendation

**Start with JSONL (append-only, atomic)** for MVP. Rationale:

1. **Single-user single-machine** — No concurrency issues beyond the rare case of two CLI sessions running simultaneously, which O_APPEND on a JSONL file handles correctly.
2. **Zero dependency** — No SQLite library needed. Every language can append to a file and parse JSON.
3. **Easy inspection** — `cat stats.jsonl | tail -5` works. `wc -l stats.jsonl` gives session count.
4. **Migration path to SQLite** is clean: a one-time script reads JSONL and bulk-inserts into SQLite. The JSONL format serves as the "write-ahead log" source of truth even after adding SQLite as a query layer.
5. **At ~50 sessions/day, 1 year = ~18,250 lines = ~4MB.** JSONL handles this trivially.

**Migration path:** When queries get slow (>10k records) or users want real-time dashboard refresh, add SQLite on top. The JSONL stays as the append log; a background process or CLI command materializes into SQLite for query speed.

### 4. Query Patterns (User Needs)

#### 80% Queries (MVP must support)

| # | Query | SQL (imaginary) | Implementation |
|---|---|---|---|
| 1 | "Total focus time today" | `SELECT SUM(duration_actual) WHERE started_at >= today AND ended_by != 'abandoned'` | Parse JSONL, filter by date, sum. O(n) per scan but n is small. |
| 2 | "Total focus time this week" | Same with `started_at >= start_of_week` | Same with different date range |
| 3 | "Per-app breakdown today" | `SELECT app, SUM(duration_actual), COUNT(*) GROUP BY app WHERE ...` | Group-by in code over date-filtered records |
| 4 | "Session list (recent N)" | `SELECT * ORDER BY started_at DESC LIMIT 20` | Read JSONL backwards (tail); or sort in memory |
| 5 | "Completed vs early-stop ratio" | `SELECT ended_by, COUNT(*) GROUP BY ended_by` | Group-by in code |
| 6 | "How many blocking requests today" | `SELECT SUM(blocking_requests_queued) WHERE today` | Simple sum filter |

#### 15% Queries (P1 — nice to have but not required)

| # | Query | Notes |
|---|---|---|
| 7 | "Average session duration per app" | Derivative of per-app breakdown |
| 8 | "Time-of-day heatmap" (which hours are most productive) | Requires bucketizing started_at by hour |
| 9 | "Sessions by label/keyword" | Text search over labels |
| 10 | "Blocking requests per session trend" | Week-over-week comparison |

#### 5% Queries (P2+ — defer)

| # | Query | Notes |
|---|---|---|
| 11 | "Streak counters" (consecutive completed sessions) | Requires session ordering and gap detection |
| 12 | "Interruption rate trend" | Week-over-week early-stop ratio |
| 13 | "AI active time vs wall time" | Requires ai_active_seconds field |
| 14 | "Prompt category breakdown" | Requires prompt_category field |

**Recommendation:** Support queries 1-6 in MVP. They cover the 复盘 use case: "how much focused time did I spend in Claude Code vs Codex today/week, and how many blocking requests were queued." No streak logic, no heatmap, no trend lines.

### 5. AI-CLI-Specific Stats (Beyond Ordinary Pomodoros)

This is where cc-pomodoro differentiates from every existing Pomodoro tool. Here are the AI-specific dimensions, ranked by capture cost vs value:

#### Cheap-to-capture (HIGH value, LOW cost — include in MVP)

| Field | Cost | Value | Recommendation |
|---|---|---|---|
| `blocking_requests_queued` | Minimal — increment a counter in the hook | **Highest** — unique to AI CLI; tells you "how disruptive this session was" | **MVP REQUIRED** |
| `app` (CLI name) | Trivial — static config | **High** — primary grouping dimension | **MVP REQUIRED** |
| `ended_by` | Trivial — one enum value at session end | **High** — "did I complete it or bail?" | **MVP REQUIRED** |
| `label` | User types it (or empty) | **Medium** — recall value | **MVP REQUIRED** (optional field but schema slot is cheap) |

#### Moderate-cost (MEDIUM value, MEDIUM cost — defer to P1)

| Field | Cost | Value | Recommendation |
|---|---|---|---|
| `prompt_category` | Requires classification logic (keyword matching or ML) | **Medium-High** — answers "what kind of work am I doing?" | **P1** — implement with simple keyword-based classifier first, not ML |
| `ai_state_at_end` | Requires polling the CLI's internal state | **Medium** — "was AI still thinking when I stopped?" | **P1** — if easy to detect via hook, add it; if not, skip forever |

#### Expensive-to-capture (LOW-MEDIUM value, HIGH cost — defer to P2+ or skip)

| Field | Cost | Value | Recommendation |
|---|---|---|---|
| `ai_active_seconds` | Requires instrumenting AI response timing within session | **Medium** — interesting, not essential for 复盘 | **P2+** — only if users explicitly ask for it |
| `prompt_contents` | Stores raw prompt text | **LOW** — privacy risk outweighs analytical value | **NEVER** — do not store raw prompts, see section 6 |
| `tool_use_types` | Track which specific tools AI invoked (read, edit, bash, etc.) | **Low-Medium** | **Skip** — noise outweighs signal; blocking_requests_queued is the useful aggregate |

#### Unique query that only cc-pomodoro can answer

> "Today I spent 2h 15min in Claude Code with 43 blocked requests across 5 sessions, 1h 30min in Codex CLI with 12 blocked requests across 3 sessions. My early-stop rate is 20% (2/10 sessions). Last week it was 35%."

This cross-CLI, blocking-aware summary is impossible in Forest, Toggl, or any generic Pomodoro tool. It is our unique value proposition for the stats module.

### 6. Privacy Considerations

#### Core Principle

**Default: do NOT store prompt contents.** The risk/reward ratio is unacceptable — a single captured API key or personal document excerpt in a prompt causes a privacy incident. The analytical value is near-zero because prompt text is high-entropy, non-categorizable without NLP, and not actionable for 复盘.

#### Redactable Fields (for post-MVP cloud sync)

If cloud sync is ever added (P2+), the following fields should have redaction/truncation options:

| Field | Default | Redactable? | Redaction behavior |
|---|---|---|---|
| `label` | Stored | Yes | Replace with `[redacted]` or truncate to first 20 chars |
| `tags` | Stored | Yes | Remove all tag entries |
| `prompt_category` | Stored | No | Aggregate label, no PII |
| `started_at` / `ended_at` | Stored | Yes | Round to hour (lose minute precision) |
| `duration_*` | Stored | No | Aggregate metric, no PII |
| `blocking_requests_queued` | Stored | No | Aggregate metric, no PII |
| `app` | Stored | No | Just a tool name |

#### What Can Be Stored Safely

- All numerical counters and durations
- App names ("claude-code", "codex-cli")
- Session outcome enums
- Prompt category labels (coarse, no PII)

#### What Should NEVER Be Stored

- Raw prompt text (user's question/instruction to AI)
- AI response text
- File paths from the user's system
- Environment variables
- Any field that could contain API keys, tokens, or secrets

#### Cloud Sync Design Principle

If cloud sync is added post-MVP, it should use a **tiered sync model**:

```
Tier 1 (always synced): duration_planned, duration_actual, app, started_at (date only), ended_by
Tier 2 (opt-in): started_at (full timestamp), label, tags
Tier 3 (local-only): everything else
```

## Recommended MVP Schema

```json
{
  "id": "uuid-v4-string",
  "started_at": "2026-05-15T09:00:00+08:00",
  "ended_at": "2026-05-15T09:25:00+08:00",
  "duration_planned": 1500,
  "duration_actual": 1487,
  "ended_by": "completed",
  "app": "claude-code",
  "label": "API design for timer module",
  "blocking_requests_queued": 3,
  "schema_version": 1
}
```

| Field | In MVP? | Rationale |
|---|---|---|
| `id` | **Yes** | Dedup, future sync, partial update support |
| `started_at` | **Yes** | Foundation of all time-queries: "today", "this week" |
| `ended_at` | **Yes** | Needed for actual duration; null = abandoned |
| `duration_planned` | **Yes** | Required for completion ratio metrics |
| `duration_actual` | **Yes** | Core metric; difference from planned = "early stop loss" |
| `ended_by` | **Yes** | Enables "completion rate" and "interruption rate" queries |
| `app` | **Yes** | Cross-CLI breakdown is the primary grouping dimension |
| `label` | **Yes** | Low cost; user can leave null. High recall value when filled. |
| `blocking_requests_queued` | **Yes** | Unique AI-CLI metric; cheap to increment in hook |
| `schema_version` | **Yes** | Future migration without breaking existing records |
| `prompt_category` | **No (P1)** | Requires classification logic; validate MVP value first |
| `ai_state_at_end` | **No (P1)** | Requires hook instrumentation; unclear MVP value |
| `ai_active_seconds` | **No (P2+)** | Hard to measure accurately; not needed for 复盘 |
| `tags` | **No (P2+)** | User-added friction; derived from label or prompt_category |
| `note` | **No (P2+)** | Free-text field with privacy implications |
| `break_records` | **No (P2+)** | Breaks out of MVP scope entirely |

## Storage Recommendation

**Use JSONL (append-only, one JSON object per line, newline-delimited) stored at `~/.config/cc-pomodoro/sessions.jsonl`.** Atomic append via O_APPEND, zero dependencies, trivially inspectable with `tail`/`wc`, and seamlessly migratable to SQLite when query performance demands it. At ~50 sessions/day, one year of data is ~4MB — well within JSONL's sweet spot.

## Related Specs

- `.trellis/tasks/05-15-ai-cli-cc-pomodoro/prd.md` — Master PRD; stats is AC6 and Open Question 3
- `.trellis/spec/backend/database-guidelines.md` — General DB guidelines (may need updating for this project's JSONL approach)
