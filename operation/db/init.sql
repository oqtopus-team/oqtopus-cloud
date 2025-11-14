-- DROP TABLE IF EXISTS main.results;
-- DROP TABLE IF EXISTS main.tasks;
-- DROP TRIGGER IF EXISTS main.update_tasks_status_trigger;
DROP TABLE IF EXISTS main.jobs;
DROP TABLE IF EXISTS main.devices;

-- drop table main.devices;
CREATE TABLE IF NOT EXISTS main.devices (
  id VARCHAR(64) PRIMARY KEY,
  device_type VARCHAR(32) DEFAULT 'QPU' NOT NULL,
  status VARCHAR(64) DEFAULT 'available' NOT NULL,
  available_at DATETIME,
  pending_jobs INT DEFAULT 0 NOT NULL,
  n_qubits INT DEFAULT 1 NOT NULL,
  basis_gates VARCHAR(256) NOT NULL,
  instructions VARCHAR(64) NOT NULL,
  device_info TEXT,
  calibrated_at DATETIME,
  description VARCHAR(128) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- drop table main.jobs;
CREATE TABLE IF NOT EXISTS main.jobs (
  id VARCHAR(64) PRIMARY KEY,
  owner VARCHAR(64) NOT NULL,
  name varchar(256) DEFAULT '' NOT NULL,
  description VARCHAR(1024),
  device_id VARCHAR(64) NOT NULL,
  job_info TEXT,
  transpiler_info TEXT,
  simulator_info TEXT,
  mitigation_info TEXT,
  job_type VARCHAR(32) DEFAULT 'sampling' NOT NULL,
  shots INT DEFAULT 1000 NOT NULL,
  status VARCHAR(32) DEFAULT 'submitted' NOT NULL,
  execution_time DECIMAL(65,3),
  submitted_at DATETIME,
  ready_at DATETIME,
  running_at DATETIME,
  ended_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

drop table if exists main.users;
CREATE TABLE IF NOT EXISTS users (
    id                serial PRIMARY KEY,
    cognito_id        VARCHAR(255) UNIQUE NOT NULL,
    email             VARCHAR(255)        NOT NULL,
    username          VARCHAR(100),
    userstatus        VARCHAR(10),
    organization      VARCHAR(255),
    group_id          VARCHAR(255),
    available_devices TEXT,
    api_token_id      VARCHAR(255) UNIQUE,
    api_token_hash    VARCHAR(255),
    api_token_expiration TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

drop table if exists main.whitelist_users;
CREATE TABLE IF NOT EXISTS whitelist_users (
    id serial PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    group_id VARCHAR(255) NOT NULL,
    is_signup_completed BOOLEAN DEFAULT FALSE,
    username VARCHAR(255),
    organization VARCHAR(255),
    available_devices TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  );

drop table if exists main.announcements;
CREATE TABLE IF NOT EXISTS announcements (
    id serial PRIMARY KEY,
    title VARCHAR(255),
    content TEXT,
    start_time DATETIME,
    end_time DATETIME,
    publishable BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  );

-- Insert devices
INSERT INTO main.devices (id, device_type, status, available_at, pending_jobs, n_qubits, basis_gates, instructions, device_info, calibrated_at, description)
SELECT 'SC', 'QPU','available', CURRENT_TIMESTAMP, 9, 64, '["sx", "rz", "rzx90", "id"]', '["measure", "barrier"]', '', CURRENT_TIMESTAMP, 'Superconducting quantum computer'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'SC');

INSERT INTO main.devices (id, device_type, status, available_at, pending_jobs, n_qubits, basis_gates, instructions, device_info, calibrated_at, description)
SELECT 'SVSim', 'simulator','available', CURRENT_TIMESTAMP, 0, 39, '["x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "cx", "cz", "swap", "u1", "u2", "u3", "u", "p", "id", "sx", "sxdg"]', '["measure", "barrier", "reset"]', '', CURRENT_TIMESTAMP, 'State vector-based quantum circuit simulator'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'SVSim');

INSERT INTO main.devices (id, device_type, status, available_at, pending_jobs, n_qubits, basis_gates, instructions, device_info, calibrated_at, description)
SELECT 'Kawasaki', 'QPU','available', CURRENT_TIMESTAMP, 2, 64, '["sx", "rz", "rzx90", "id"]', '["measure", "barrier"]', '', CURRENT_TIMESTAMP, 'Superconducting quantum computer'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'Kawasaki');

INSERT INTO main.devices (id, device_type, status, available_at, pending_jobs, n_qubits, basis_gates, instructions, device_info, calibrated_at, description)
SELECT '01927422-86d4-7597-b724-b08a5e7781fc', 'QPU','unavailable', CURRENT_TIMESTAMP, 0, 64, '["sx", "rz", "rzx90", "id"]', '["measure", "barrier"]', '', CURRENT_TIMESTAMP, 'Superconducting quantum computer'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = '01927422-86d4-7597-b724-b08a5e7781fc');

-- Insert jobs
INSERT INTO main.jobs (id, owner, name, description, device_id, job_info, transpiler_info, simulator_info, mitigation_info, job_type, shots, status, submitted_at)
SELECT '01927422-86d4-73d6-abb4-f2de6a4f5910', 'admin', 'Test job 1', 'Test job 1 description', 'Kawasaki', '{\'code\': \'todo\'}', '', '', '', 'sampling', 1000, 'submitted', CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT * FROM main.jobs WHERE owner = 'admin' AND name = 'Test job 1');

INSERT INTO main.jobs (id, owner, name, description, device_id, job_info, transpiler_info, simulator_info, mitigation_info, job_type, shots, status, submitted_at)
SELECT '01927422-86d4-7cbf-98d3-32f5f1263cd9', 'admin', 'Test job 2', 'Test job 2 description', 'Kawasaki', '{\'code\': \'todo\'}', '', '', '', 'sampling', 1000, 'submitted', CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT * FROM main.jobs WHERE owner = 'admin' AND name = 'Test job 2');
