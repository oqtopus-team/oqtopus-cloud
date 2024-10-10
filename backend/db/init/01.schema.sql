drop table main.devices;
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

drop table main.jobs;
CREATE TABLE IF NOT EXISTS main.jobs (
  id VARBINARY(64) PRIMARY KEY,
  owner VARCHAR(64) NOT NULL,
  name varchar(256) DEFAULT '' NOT NULL,
  description VARCHAR(1024),
  device_id VARCHAR(64) NOT NULL,
  job_detail TEXT,
  transpiler_info TEXT,
  simulator_info TEXT,
  mitigation_info TEXT,
  job_type VARCHAR(32) DEFAULT 'sampling' NOT NULL,
  shots INT DEFAULT 1000 NOT NULL,
  status VARCHAR(32) DEFAULT 'submitted' NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
