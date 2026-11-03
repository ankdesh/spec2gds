# Spec Component Library

The Spec Component Library provides verified, reusable digital hardware Components packaged in self-contained `.spec` files.

## 1. Designer Usage Workflow

1. **Start the local catalogue service**:
   ```bash
   uv run spec2gds-library-service --host 127.0.0.1 --port 6017 --library-root spec_library --state-dir spec_library/.state
   ```
2. **Browse the catalogue**:
   Open `http://127.0.0.1:6017/` in a web browser. Search for Components by ID, category, or tag.
3. **Inspect presets and verification evidence**:
   Review parameter configurations, timing characteristics, and pass/fail evidence records before integrating.
4. **Download an exact version**:
   Download the canonical `<id>.spec` package for your selected version.
5. **Use in your project**:
   Save a working copy inside your project directory. Open the copy using Spec Editor or Circuit Designer.
   Record the origin VLNV (`spec2gds.local:<category>:<id>:<version>`) and package SHA-256 digest in your project notes.
   Local edits must never alter published library files; released VLNVs are immutable.

## 2. Directory Layout

```text
spec_library/
  README.md                         # Designer usage guide
  inventory.json                    # Canonical inventory index
  handoffs/                         # Phase completion handoffs
  <category>/<id>/<version>/
    <id>.spec                       # Self-contained IP-XACT component package
    evidence.json                   # Verified execution records and digests
    usage.md                        # Documentation: interface, timing, examples
  .state/                           # Ignored SQLite service index
```

## 3. Library Management CLI

- **Check library integrity**:
  ```bash
  uv run spec2gds-library check --phase 1 --output spec_library/TEMP_p1/check
  ```
- **Verify components**:
  ```bash
  uv run spec2gds-library verify --phase 1 --output spec_library/TEMP_p1/verify
  ```
- **Publish candidates**:
  ```bash
  uv run spec2gds-library publish --phase 1 --candidates spec_library/TEMP_p1/candidates --evidence spec_library/TEMP_p1/verify --output spec_library/TEMP_p1/publish
  ```
- **Rebuild service index**:
  ```bash
  uv run spec2gds-library index --library-root spec_library --state-dir spec_library/.state
  ```
