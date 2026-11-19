# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-19

### Added

- Local-first Polar AccessLink v3 ingestion with OAuth2, catch-up sync, FIT
  parsing and DuckDB persistence.
- Banister TRIMP for running and elliptical sessions, Foster session-RPE for
  strength sessions and contiguous daily-load assembly.
- Banister fitness-fatigue model with an exact daily recurrence and a
  `solve_ivp` cross-check.
- Individualized calibration with fixed time constants, bounded ridge least
  squares and a leave-one-out cross-validation gate.
- Acute:chronic workload ratio with exponentially weighted moving averages and
  four risk zones.
- Dash + Mantine dashboard with Today, Trends and Plan views, readiness, ACWR,
  fitness-fatigue, aerobic decoupling, session editing and RPE capture.
- What-if simulator, race-taper planner, running baseline and race-time
  prediction using Riegel, critical speed or heart-rate extrapolation.
- Docker Compose deployment, Makefile workflow, GitHub Actions CI and an 80 %
  core-coverage gate.
- Public documentation set and a real-data validation report.

### Changed

- Replaced the historical EKF calibration with the NLS/ridge calibration path.
- Optimized metric reads with batch queries, a revision-keyed snapshot cache and
  lightweight sample rows.

### Removed

[Unreleased]: https://github.com/Alejandro-Vallejo-Mayo/athlete-stress-sim/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Alejandro-Vallejo-Mayo/athlete-stress-sim/releases/tag/v1.0.0
