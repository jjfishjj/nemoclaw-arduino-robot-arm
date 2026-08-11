# Runtime secrets

This directory contains documentation only. Never commit real credentials or keys.
For the secure Compose overlay create locally:

- `postgres_password.txt`
- `database_url.txt`
- `api_key.txt`
- `mosquitto/ca.crt`, `server.crt`, `server.key`
- `mosquitto/client.crt`, `client.key`, and a Mosquitto `passwords` file

Generate certificates through your organization PKI or a documented development CA.
Restrict files to the service account (`chmod 600`). Rotate API/database/MQTT secrets
independently and keep production values in a secrets manager.
