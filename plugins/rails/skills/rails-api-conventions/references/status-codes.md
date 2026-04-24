# API status codes

- `200 OK` — successful GET/PUT/PATCH
- `201 Created` — successful POST that created a resource
- `204 No Content` — successful DELETE (or PUT with no body to return)
- `400 Bad Request` — malformed JSON, missing required param structure
- `401 Unauthorized` — missing or invalid auth
- `403 Forbidden` — authenticated but not permitted
- `404 Not Found` — resource doesn't exist (or you don't want to leak its existence)
- `409 Conflict` — state conflict (e.g. duplicate unique field)
- `422 Unprocessable Entity` — validation failure. Standard Rails signal for `save`/`update` returning false.
