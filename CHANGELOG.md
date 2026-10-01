# Changelog

All notable changes to PipeSync are documented here.

## [1.1.0] - 2026-10-01

### Added

- Automated GitHub Actions checks for unit tests and wheel builds.
- Release metadata verification in CI.
- Project audit covering known defects, limitations, and follow-up work.

### Fixed

- Calibration audio now works from installed wheels without repository files.
- Settings and profile writes are atomic to avoid truncated JSON after interruption.
- Malformed PipeWire latency data no longer aborts device discovery.
- Failed PipeWire channel links are rejected instead of being reported as active.
- Empty or failed synchronization starts clean up the virtual master sink.

### Packaging

- Centralized the project version at `pipesync.__version__`.
- Included the desktop launcher in the wheel under `share/applications`.
- Added repository, homepage, and issue tracker metadata.

## [1.0.0] - Initial release

- Initial PipeWire multi-device synchronization engine, CLI, GUI, calibration
  helper, and Helvum integration.
