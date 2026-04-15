# Database

The backend uses **SQLite** via Python's built-in `sqlite3` module. The database file is stored at the path configured by the `DB_PATH` environment variable (default: `spelling_bee.db` in the backend working directory).

---

## Schema

### `users`

Stores user accounts.

```sql
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    spelling_speed  TEXT NOT NULL DEFAULT 'normal',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_admin        INTEGER NOT NULL DEFAULT 0
);
```

| Column | Description |
|---|---|
| `id` | Auto-increment primary key |
| `username` | Unique login handle |
| `hashed_password` | bcrypt hash of the user's password |
| `spelling_speed` | `slow` \| `normal` \| `fast` |
| `created_at` | Account creation timestamp |
| `is_admin` | `1` = admin, `0` = regular user |

---

### `game_sessions`

One row per played game.

```sql
CREATE TABLE IF NOT EXISTS game_sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT UNIQUE NOT NULL,
    user_id        INTEGER REFERENCES users(id),
    started_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at       TIMESTAMP,
    total_words    INTEGER,
    correct_count  INTEGER,
    spelling_speed TEXT
);
```

| Column | Description |
|---|---|
| `session_id` | UUID generated per WebSocket connection |
| `user_id` | FK to `users.id`; NULL for anonymous sessions |
| `ended_at` | Set when the game ends (normally or via quit) |
| `total_words` | Number of words presented (always ≤ 10) |
| `correct_count` | Number of correct spellings |
| `spelling_speed` | Speed used in this session (snapshot at game start) |

---

### `spelling_attempts`

One row per user turn — each time the user spells a word, repeats, skips, or quits.

```sql
CREATE TABLE IF NOT EXISTS spelling_attempts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    user_id      INTEGER REFERENCES users(id),
    word         TEXT NOT NULL,
    attempt      TEXT,
    correct      INTEGER NOT NULL DEFAULT 0,
    command_type TEXT,
    timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Description |
|---|---|
| `word` | The challenge word |
| `attempt` | The normalised text of what the user said |
| `correct` | `1` = correct spelling, `0` = incorrect or command |
| `command_type` | `repeat` \| `skip` \| `quit` \| NULL for spelling attempts |

---

### `unhandled_interruptions`

Telemetry table for out-of-scope utterances. Used to improve the classifier and discover unsupported commands.

```sql
CREATE TABLE IF NOT EXISTS unhandled_interruptions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id   TEXT,
    user_id      INTEGER REFERENCES users(id),
    raw_text     TEXT,
    normalized   TEXT,
    phase        TEXT,
    current_word TEXT
);
```

| Column | Description |
|---|---|
| `raw_text` | The raw STT transcription |
| `normalized` | Lowercase stripped version |
| `phase` | Game phase when the utterance occurred |
| `current_word` | The word being spelled at the time |

---

## Repository layer

Each table has a dedicated repository class in `backend/db/repositories/`.

| Repository | File | Responsibility |
|---|---|---|
| `UserRepository` | `user.py` | create, find_by_id, find_by_username, update_speed |
| `GameSessionRepository` | `game_session.py` | open_session, close_session |
| `SpellingAttemptRepository` | `spelling_attempt.py` | insert attempt or command |
| `TelemetryRepository` | `telemetry.py` | insert unhandled utterance |
| `MetricsRepository` | `metrics.py` | aggregated queries for admin dashboard |

All repositories instantiate their own `sqlite3.connect()` connection per call (connection-per-request pattern). The SQLite WAL mode is not explicitly enabled; for write-heavy workloads consider adding `PRAGMA journal_mode=WAL`.

---

## Persistence in Docker

When running via Docker Compose the database file is stored inside the container and lost on rebuild unless mounted as a volume. The provided `docker-compose.yml` mounts `./backend/data` on the host to `/app/data` inside the container and sets `DB_PATH=/app/data/spelling_bee.db`.

To back up the database:

```bash
cp backend/data/spelling_bee.db spelling_bee_backup_$(date +%Y%m%d).db
```
