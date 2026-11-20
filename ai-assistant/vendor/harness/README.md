# Pinned Harness archives

These 175 original npm archives belong to release `0.1.6-ankdesh.2`. They total
6,361,720 bytes. They are application dependencies, not temporary build output.

`../../releases/harness-release-manifest.json` records each archive filename,
version, SHA-256, SHA-512 integrity value, and licence files. Its checksum is pinned
in `../../harness.lock.json`. The archives retain their original licence files and
third-party notices. Do not edit or repack them.

From the repository root, run:

```sh
scripts/setup-all.sh
```

For Assistant dependencies alone, run:

```sh
npm --prefix ai-assistant run install:packages
```

The installer verifies all archives before npm extracts them into `node_modules`.
No GitHub package token is needed. Public npm dependencies still require network
access. The current native addon targets Linux x86-64 with glibc.

For release updates, use `scripts/adopt-harness-release.mjs` with the promoted
release and its consumer verification evidence. Include the original archives
beside the release manifest. See `docs/harness-packages.md` at the repository root.
