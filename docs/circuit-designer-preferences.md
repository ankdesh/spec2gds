# Circuit Designer preferences

Circuit Designer has one shared preference profile for every browser connected
to its local/shared service. It is intentionally not tied to a user account.
The last successful write wins.

## Profile and location

The current contract is `CircuitDesignerPreferencesV1`:

```json
{
  "schema_version": 1,
  "ui": {
    "inspector_open": false
  },
  "action_bindings": {
    "new-document": {
      "keyboard": "Mod+N",
      "mouse": "none"
    }
  }
}
```

The complete saved profile contains every registered action. The default path
is `generated/circuit-designer/preferences.json`, selected by
`circuit_designer.preferences_file` in `config/services.json`. Set
`CIRCUIT_DESIGNER_PREFERENCES_FILE` to override that path.

The service returns defaults without creating a file when the configured file
is missing. The first preference update creates its parent directory and writes
the profile atomically using a same-directory temporary file and rename. A
malformed existing file produces a validation error and is never overwritten by
a read.

## REST API

- `GET /api/circuit-designer/v1/preferences` returns `{ preferences,
  persisted }`. `persisted` is false when defaults came from a missing file.
- `PUT /api/circuit-designer/v1/preferences` accepts the V1 profile, writes it,
  and returns `{ preferences, persisted: true }`.

Requests and files are limited to 256 KiB. Validation rejects unsupported
schema versions, unknown action IDs, keyboard strings longer than 64
characters, unsupported mouse values, and malformed bindings. Missing known
actions are merged from current defaults so an older valid profile gains newly
introduced commands on its next read or write.

## Browser behavior

The preferences page applies changes immediately in memory and saves after a
short debounce. It shows loading, saving, saved, and failure states. The server
file is authoritative after the initial load.

Older browser-local action bindings migrate only when the server reports that
no profile exists. After migration, local storage is cleared. Local storage is
otherwise used only as a failed-save cache so a temporary service failure does
not lose edits before the next load.

Assigning a keyboard or mouse input already owned by another command removes
that input from the previous command. This keeps the centralized menu,
keyboard, and canvas mouse executor conflict-free.
