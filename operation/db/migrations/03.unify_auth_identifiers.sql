ALTER TABLE main.users ADD COLUMN user_identifier VARCHAR(255) NOT NULL AFTER cognito_id;
UPDATE main.users SET user_identifier = email;
ALTER TABLE main.users
MODIFY COLUMN user_identifier VARCHAR(255) NOT NULL,
ADD UNIQUE INDEX user_identifier (user_identifier);
-- ALTER TABLE main.users DROP COLUMN email;
ALTER TABLE main.users RENAME COLUMN username TO display_name;

ALTER TABLE main.whitelist_users RENAME COLUMN username TO display_name;