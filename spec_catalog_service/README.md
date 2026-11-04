# Spec Catalog service

The Spec Catalog service hosts reusable Component releases and their verification evidence. It is a separate UV workspace package. The Spec service accesses it through HTTP.

Run `uv sync --all-packages` from the repository root. If you use document import, add `--extra document-import` when you sync the workspace. Start the complete environment with `scripts/serve-all.sh start`. The catalog listens on port 6017 by default. The shared service configuration controls its listener, `catalog_root`, and `state_dir`. The launcher also accepts `--catalog-port`.

To start only the catalog:

```bash
uv run --package spec-catalog-service spec2gds-catalog-service --service-config config/services.json
```

The HTTP prefix is `/api/spec-catalog/v1`. The standalone browser UI is at the service root. Startup reconstructs the SQLite index from durable package and evidence files. Catalog releases are immutable.

In Spec Editor, open **Components → Options → Import from catalog…**. Search or filter the published releases, select an exact version, and select **Review import**. Resolve conflicts with **Import as a renamed copy**, then select **Import into Spec**. The imported definition is an editable, self-contained local copy. Its published parameter defaults remain in place. Add instances through a Design's Options menu.

The Component's **Catalog origin** details identify its source release. Published evidence and verification of the current Spec are separate records. **Options → Generate RTL** verifies the saved target before it starts the Activity. **Options → Verify Component** and **Verify Design** also remain available.

## Layout and commands

- `src/spec_catalog_service/http/`: hosting, storage, indexing queries, and standalone UI.
- `src/spec_catalog_service/catalog/`: Component definitions, authoring, verification, publishing, and index reconstruction.
- `catalog/`: inventory, published `.spec` files, usage documents, and durable evidence.
- `tests/`: service, storage, schema, and index tests.
- `.state/`: ignored, derived SQLite index.

```bash
uv run --package spec-catalog-service spec2gds-catalog check --phase 1 --output temp/TEMP_catalog_check
uv run --package spec-catalog-service spec2gds-catalog verify --phase 1 --output temp/TEMP_catalog_verify
uv run --package spec-catalog-service spec2gds-catalog index --catalog-root spec_catalog_service/catalog --state-dir spec_catalog_service/.state
```

The old library commands, Python modules, and HTTP routes have been removed. Published package bytes and their embedded metadata identifiers remain unchanged. Stop an older environment before updating, then start it with the updated launcher.
