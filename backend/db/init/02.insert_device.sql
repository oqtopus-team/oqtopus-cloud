INSERT INTO main.devices (id, device_type,status, n_qubits, n_nodes, basis_gates, instructions, description)
SELECT 'SC', 'QPU','AVAILABLE', 64, NULL, '["sx", "rz", "rzx90", "id"]', '["measure", "barrier"]', 'Superconducting quantum computer'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'SC');

INSERT INTO main.devices (id, device_type, status, n_qubits, n_nodes, basis_gates, instructions, description)
SELECT 'SVSim', 'simulator','AVAILABLE', 39, 512, '["x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "cx", "cz", "swap", "u1", "u2", "u3", "u", "p", "id", "sx", "sxdg"]', '["measure", "barrier", "reset"]', 'State vector-based quantum circuit simulator'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'SVSim');

INSERT INTO main.devices (id, device_type, status, n_qubits, n_nodes, basis_gates, instructions, description)
SELECT 'Kawasaki', 'QPU','AVAILABLE', 64, NULL, '["sx", "rz", "rzx90", "id"]', '["measure", "barrier"]', 'Superconducting quantum computer'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'Kawasaki');

INSERT INTO main.devices (id, device_type, n_qubits, n_nodes, basis_gates, instructions, description)
SELECT 'test1', 'QPU', 64, NULL, '["sx", "rz", "rzx90", "id"]', '["measure", "barrier"]', 'Superconducting quantum computer'
WHERE NOT EXISTS (SELECT * FROM main.devices WHERE id = 'test');
