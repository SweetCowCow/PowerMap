## MODIFIED Requirements

### Requirement: Official snapshot download

The system SHALL provide `make official-download`, which downloads datasets 8934 (`thermal_hydro.csv`), 10858 (`nuclear.csv`), 17141 (`renewable.csv`) and 8931 (`units.json`) into `data/official/raw/<YYYY-MM-DD>/` named after the UTC download date, and writes `manifest.json` in that directory with `downloaded_at`, `license` (`政府資料開放授權條款第1版`) and, per file, `dataset_id`, `title`, `url`, `file` and `sha256`. Files SHALL be written to a temporary directory and moved into place only after all four downloads succeed. The system SHALL refuse to overwrite an existing date directory and exit non-zero, unless the download command is given `--reuse-existing`, in which case it SHALL keep the existing directory, download nothing and exit 0. `make data` SHALL NOT access the network for official data.

#### Scenario: Successful download creates a dated snapshot

- **WHEN** `make official-download` runs on 2026-11-12 and all four downloads succeed
- **THEN** `data/official/raw/2026-11-12/` contains the four files and a `manifest.json` whose `files` entries carry the SHA-256 of each file

#### Scenario: Failed download leaves no partial snapshot

- **WHEN** one of the four downloads fails
- **THEN** the command exits non-zero and no `data/official/raw/<date>/` directory is created

#### Scenario: Existing snapshot is not overwritten

- **WHEN** `data/official/raw/2026-11-12/` already exists and the download runs again on the same day
- **THEN** the command exits non-zero with a message naming the existing directory

#### Scenario: Existing snapshot is reused on request

- **WHEN** `data/official/raw/2026-11-12/` already exists and the download runs again on the same day with `--reuse-existing`
- **THEN** the command exits 0, prints that it reuses the existing directory and leaves its files unchanged
