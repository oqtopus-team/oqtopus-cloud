INSERT INTO main.jobs (id, owner, name, description, device_id, job_info, transpiler_info, simulator_info, mitigation_info, job_type, shots, status)
SELECT '01927422-86d4-73d6-abb4-f2de6a4f5910', 'admin', 'Test job 1', 'Test job 1 description', 'Kawasaki', '{\'code\': \'todo\'}', '', '', '', 'sampling', 1000, 'submitted'
WHERE NOT EXISTS (SELECT * FROM main.jobs WHERE owner = 'admin' AND name = 'Test job 1');

INSERT INTO main.jobs (id, owner, name, description, device_id, job_info, transpiler_info, simulator_info, mitigation_info, job_type, shots, status)
SELECT '01927422-86d4-7cbf-98d3-32f5f1263cd9', 'admin', 'Test job 2', 'Test job 2 description', 'Kawasaki', '{\'code\': \'todo\'}', '', '', '', 'sampling', 1000, 'submitted'
WHERE NOT EXISTS (SELECT * FROM main.jobs WHERE owner = 'admin' AND name = 'Test job 2');

