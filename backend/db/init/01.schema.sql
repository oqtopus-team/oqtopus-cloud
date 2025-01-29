drop table if exists main.devices;
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

drop table if exists main.jobs;
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
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

drop table if exists main.users;
CREATE TABLE IF NOT EXISTS users (
    id                serial PRIMARY KEY,
    cognito_id        VARCHAR(255) UNIQUE NOT NULL,
    email             VARCHAR(255)        NOT NULL,
    username          VARCHAR(100),
    userstatus        Integer,
    api_token_secret VARCHAR(255) UNIQUE,
    organization      VARCHAR(255),
    purpose           VARCHAR(255),
    group_id VARCHAR(255),
    require_mfa_reset BOOLEAN,
    api_token_expiration TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
);

drop table if exists main.whitelist_users;
CREATE TABLE IF NOT EXISTS whitelist_users (
    id serial PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    group_id VARCHAR(255) NOT NULL,
    is_signup_completed BOOLEAN DEFAULT FALSE,
    username VARCHAR(255),
    organization VARCHAR(255),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  );
