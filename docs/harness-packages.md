# Harness package releases

Normal spec2gds setup installs locked `@ankdesh` packages from GitHub Packages.
It does not clone or build DeepSeek Harness. The [HTML guide](harness-packages/index.html)
explains the registry, package contents, and release process.

## Install and run

Set `NODE_AUTH_TOKEN` to a GitHub classic personal access token with `read:packages`.
Do not store its value in tracked files. Grant the spec2gds repository package read
access before using its Actions token.

```sh
npm --prefix ai-assistant ci
npm --prefix ai-assistant run build
npm --prefix ai-assistant run dev -- --no-open
```

The first package release must be published and adopted before registry installation
can succeed. The Harness lock records `pending-publication` until adoption. Local
candidate verification uses a separate read-only registry and does not promote a release.

## Create a release

The Harness worktree contains `scripts/package-release/pack.mjs`, `verify.mjs`,
`acceptance.mjs`, and `publish.mjs`. Start from the shared package branch and a clean commit. Use the
manual **Private product packages** Actions flow. Supply the exact spec2gds commit
and a new `ankdesh.N` suffix. The source checkout requires a configured
`CONSUMER_READ_TOKEN` when the spec2gds repository is private.
The required live model checks use the `OPENAI_API_KEY` Actions secret. Optional
`OPENAI_BASE_URL` and `OPENAI_MODEL` Actions variables select the configured endpoint
and model. Missing credentials or incomplete checks prevent publication.

The build job has no package write token. It builds the selected archives, builds
spec2gds against a candidate registry, verifies independent production locks and
assembled releases, and runs the required fast, integration, and regression profiles.
The separate `package-release` environment publishes the tested bytes. It refuses
a dirty candidate, failed verification, changed checksums, and conflicting registry versions.
Only complete publication creates a promotion receipt.
The receipt records test results and the checksums of the verification file and
production locks. The release includes `consumer-verification.tgz`, with those
locks, installed-size measurements, and compact application test reports.

Package visibility is private on first GitHub publication. Confirm this setting,
link the packages to `ankdesh/deepseek-harness`, and grant consuming repositories
read access. Configure environment protection in GitHub if required by the project.

## Adopt a release

Download the promoted release manifest, receipt, and `consumer-verification.tgz`.
Extract the archive and use its `consumer-verification` directory as the verified
consumer directory. From `ai-assistant`:

```sh
node scripts/adopt-harness-release.mjs PROMOTED_RELEASE_DIRECTORY VERIFIED_CONSUMER_DIRECTORY
npm ci
npm run build
```

Run the required application checks. Commit the updated manifests, development
lock, production locks, release manifest, and Harness lock together. A failed or
incomplete release must not update the application lock.

## Production profiles

The first release is not yet available. The publication gate remains closed until
the required application acceptance checks pass against the candidate archives.
The production lock files will be created and adopted after those checks pass and
all packages are published. The commands below require that promoted release.

The web and headless profiles use independent production roots. The application
build supplies its own bundles; GitHub supplies the locked Harness dependencies.

```sh
npm --prefix ai-assistant run install:profile -- spec2gds-headless TEMP_headless_install
ASSISTANT_INSTALL_ROOT="$PWD/TEMP_headless_install" \
  npm --prefix ai-assistant run package -- "$PWD/TEMP_headless_release" spec2gds-headless
```

Use a new output directory each time. Release assembly checks the release manifest
checksum, follows installed package metadata, and keeps dependency links inside the
output. Native files target Linux x86-64 with glibc. Additional platforms need
separate built-artifact checks.

## Explicit source development

Harness contributors can select a compatible built checkout. It must contain the
modules used by the selected profile. The web profile requires the extracted
`@deepseek-ai/dsh-web-runtime` package in that source checkout.

```sh
cd ai-assistant
node scripts/link-harness.mjs /absolute/path/to/deepseek-harness
HARNESS_SOURCE=/absolute/path/to/deepseek-harness npm run dev:source -- --no-open
```

This mode changes local development links. Run the locked registry install again
before testing a release. Do not mix source links into a production installation.
The source mode uses the upstream package scope inside its generated runtime copy;
released application files use `@ankdesh` throughout.

## Package measurements

The release manifest lists direct roots, indirect Harness packages, archive bytes,
unpacked bytes, browser files, native files, and dependency reasons. The clean
consumer evidence includes all installed third-party packages. An untrimmed npm
baseline is measurement-only and cannot be published by this pipeline.

The old `s-workflow` execution packages and catalogues are excluded. The core
conversation decoder retains its known historical event type. A regression test
reads an old event without loading the retired packages and checks that its bytes
remain unchanged.
