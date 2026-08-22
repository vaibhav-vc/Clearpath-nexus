-- ClearPath Nexus: route ownership, dispatch lifecycle, and train scheduling.
-- Safe additive migration for an existing PostgreSQL/PostGIS database.

BEGIN;

ALTER TABLE generated_routes
    ADD COLUMN IF NOT EXISTS user_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS dispatch_status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    ADD COLUMN IF NOT EXISTS dispatched_at TIMESTAMPTZ;

-- Existing rows predate user ownership. Keep them inaccessible to authenticated
-- user-scoped history rather than guessing an owner.
UPDATE generated_routes
SET user_id = 'legacy_unowned'
WHERE user_id IS NULL;

ALTER TABLE generated_routes
    ALTER COLUMN user_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_generated_routes_user_id
    ON generated_routes (user_id);
CREATE INDEX IF NOT EXISTS ix_generated_routes_dispatch_status
    ON generated_routes (dispatch_status);

CREATE TABLE IF NOT EXISTS train_schedules (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    generated_route_id UUID NULL REFERENCES generated_routes(id),
    train_code VARCHAR(20) NOT NULL,
    train_name VARCHAR(100) NOT NULL,
    source_station_code VARCHAR(10) NOT NULL,
    dest_station_code VARCHAR(10) NOT NULL,
    scheduled_departure TIMESTAMPTZ NOT NULL,
    scheduled_arrival TIMESTAMPTZ NOT NULL,
    berth_window_start TIMESTAMPTZ NULL,
    berth_window_end TIMESTAMPTZ NULL,
    schedule_status VARCHAR(20) NOT NULL DEFAULT 'PLANNED',
    conflict_status VARCHAR(20) NOT NULL DEFAULT 'CLEAR',
    conflict_reason VARCHAR(255) NULL,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    dispatched_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_train_schedules_user_id
    ON train_schedules (user_id);
CREATE INDEX IF NOT EXISTS ix_train_schedules_generated_route_id
    ON train_schedules (generated_route_id);
CREATE INDEX IF NOT EXISTS ix_train_schedules_scheduled_departure
    ON train_schedules (scheduled_departure);
CREATE INDEX IF NOT EXISTS ix_train_schedules_schedule_status
    ON train_schedules (schedule_status);

COMMIT;
