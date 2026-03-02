SET time_zone = '+00:00';

ALTER TABLE main.devices MODIFY COLUMN available_at TIMESTAMP;
ALTER TABLE main.devices MODIFY COLUMN calibrated_at TIMESTAMP;

ALTER TABLE main.jobs MODIFY COLUMN submitted_at TIMESTAMP;
ALTER TABLE main.jobs MODIFY COLUMN ready_at TIMESTAMP;
ALTER TABLE main.jobs MODIFY COLUMN running_at TIMESTAMP;
ALTER TABLE main.jobs MODIFY COLUMN ended_at TIMESTAMP;

ALTER TABLE main.announcements MODIFY COLUMN start_time TIMESTAMP;
ALTER TABLE main.announcements MODIFY COLUMN end_time TIMESTAMP;
