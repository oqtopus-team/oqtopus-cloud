ALTER TABLE main.users RENAME COLUMN username TO display_name;

ALTER TABLE main.whitelist_users RENAME COLUMN username TO display_name;

ALTER TABLE main.users DROP PRIMARY KEY;

ALTER TABLE main.users
MODIFY COLUMN id VARCHAR(255) NOT NULL;

UPDATE main.users
SET id = email;

ALTER TABLE main.users
ADD PRIMARY KEY (id);
