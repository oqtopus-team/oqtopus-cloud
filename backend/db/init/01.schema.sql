CREATE TABLE IF NOT EXISTS main.devices (
  id VARCHAR(64) PRIMARY KEY,
  device_type ENUM ('QPU', 'simulator') NOT NULL,
  status ENUM ('AVAILABLE', 'NOT_AVAILABLE') DEFAULT 'NOT_AVAILABLE' NOT NULL,
  restart_at DATETIME,
  pending_tasks INT DEFAULT 0 NOT NULL,
  n_qubits INT NOT NULL,
  n_nodes INT,
  basis_gates VARCHAR(256) NOT NULL,
  instructions VARCHAR(64) NOT NULL,
  calibration_data TEXT,
  calibrated_at DATETIME,
  description VARCHAR(128) NOT NULL
);

-- INSERT INTO main.devices (id, device_type, n_qubits, n_nodes, basis_gates, instructions, description)
-- SELECT 'SC', 'QPU', 64, NULL, '["sx", "rz", "rzx90", "id"]', '["measure", "barrier"]', 'Superconducting quantum computer'
-- WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'SC');

-- INSERT INTO main.devices (id, device_type, n_qubits, n_nodes, basis_gates, instructions, description)
-- SELECT 'SVSim', 'simulator', 39, 512, '["x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "cx", "cz", "swap", "u1", "u2", "u3", "u", "p", "id", "sx", "sxdg"]', '["measure", "barrier", "reset"]', 'State vector-based quantum circuit simulator'
-- WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'SVSim');


CREATE TABLE IF NOT EXISTS main.tasks (
  id VARBINARY(16) PRIMARY KEY,
  owner VARCHAR(64) NOT NULL,
  name varchar(256),
  device VARCHAR(64) NOT NULL,
  n_qubits INT,
  n_nodes INT,
  code TEXT NOT NULL,
  action ENUM ('sampling', 'estimation') NOT NULL,
  method ENUM ('state_vector', 'sampling'),
  shots INT,
  operator VARCHAR(1024),
  qubit_allocation TEXT,
  skip_transpilation BOOLEAN DEFAULT false NOT NULL,
  seed_transpilation INT,
  seed_simulation INT,
  n_per_node INT UNSIGNED,
  simulation_opt text,
  ro_error_mitigation enum('none', 'pseudo_inverse', 'least_square'),
  note VARCHAR(1024),
  status ENUM ('QUEUED', 'QUEUED_FETCHED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLING', 'CANCELLING_FETCHED', 'CANCELLED') NOT NULL DEFAULT 'QUEUED',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device) REFERENCES devices(id)
);

CREATE TABLE IF NOT EXISTS main.results (
  task_id VARBINARY(16) PRIMARY KEY,
  status ENUM('SUCCESS', 'FAILURE', 'CANCELLED') NOT NULL,
  result TEXT,
  reason TEXT,
  transpiled_code TEXT,
  qubit_allocation TEXT,
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

delimiter $$

CREATE TRIGGER main.update_tasks_status_trigger
AFTER INSERT ON main.results
FOR EACH ROW
BEGIN
	IF NEW.status = 'SUCCESS' THEN
  		UPDATE main.tasks SET status = 'COMPLETED' WHERE id = NEW.task_id;
  	ELSEIF NEW.status = 'FAILURE' THEN
  		UPDATE main.tasks SET status = 'FAILED' WHERE id = NEW.task_id;
  	ELSEIF NEW.status = 'CANCELLED' THEN
  		UPDATE main.tasks SET status = 'CANCELLED' WHERE id = NEW.task_id;
  	END IF;
END$$

delimiter ;
