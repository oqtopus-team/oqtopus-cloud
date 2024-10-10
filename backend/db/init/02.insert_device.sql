INSERT INTO main.devices (id, device_type, status, available_at, pending_jobs, n_qubits, basis_gates, instructions, device_info, calibrated_at, description)
SELECT 'SC', 'QPU','available', CURRENT_TIMESTAMP, 9, 64, NULL, '["sx", "rz", "rzx90", "id"]', '["measure", "barrier"]', 'Superconducting quantum computer'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'SC');

INSERT INTO main.devices (id, device_type, status, n_qubits, n_nodes, basis_gates, instructions, description)
SELECT 'SVSim', 'simulator','available', CURRENT_TIMESTAMP, 0, 39, 512, '["x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "cx", "cz", "swap", "u1", "u2", "u3", "u", "p", "id", "sx", "sxdg"]', '["measure", "barrier", "reset"]', 'State vector-based quantum circuit simulator'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'SVSim');

INSERT INTO main.devices (id, device_type, status, n_qubits, n_nodes, basis_gates, instructions, description)
SELECT 'Kawasaki', 'QPU','available', CURRENT_TIMESTAMP, 2, 64, NULL, '["sx", "rz", "rzx90", "id"]', '["measure", "barrier"]', 'Superconducting quantum computer'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'Kawasaki');

INSERT INTO main.devices (id, device_type, n_qubits, n_nodes, basis_gates, instructions, description)
SELECT '01927422-86d4-7597-b724-b08a5e7781fc', 'QPU','unavailable', CURRENT_TIMESTAMP, 0, 64, NULL, '["sx", "rz", "rzx90", "id"]', '["measure", "barrier"]', 'Superconducting quantum computer'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'test');
