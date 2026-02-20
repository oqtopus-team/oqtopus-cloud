ALTER TABLE main.jobs ADD output_files TEXT AFTER mitigation_info;
ALTER TABLE main.jobs ADD message TEXT AFTER output_files;
