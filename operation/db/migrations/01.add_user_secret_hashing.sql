ALTER TABLE main.users DROP COLUMN api_token_secret;
ALTER TABLE main.users ADD api_token_id VARCHAR(255) UNIQUE AFTER available_devices;
ALTER TABLE main.users ADD api_token_hash VARCHAR(255) AFTER api_token_id;
