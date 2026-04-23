# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.3] - 2026-04-23

### Added
- **Smart Result Guard**: Implemented in `LandmarkBridge` to prevent context bloat. Safely compacts minimal success responses while preserving critical JSON data (like `order_id`).
- **List Truncation Logic**: Improved navigation accuracy in large registries with precise item counting (e.g., `(+45 items)`).
- **Global `Elemm` Export**: Simplified imports. Developers can now use `from elemm import Elemm` instead of deep integration paths.
- **Improved Remedy System**: Unified remedy injection in `FastAPIProtocolManager`. Remedies are now centrally managed via decorators, keeping backend exceptions clean and standard-compliant.

### Changed
- **Package Refactoring**: Consolidated `FastAPIProtocolManager` and related integrations under `elemm.integrations`.
- **Strict Parameter Validation**: Updated `smart_home` example to use strict boolean `is_on` parameters, supported by automated protocol remedies for agent self-correction.
- **Standardized Examples**: Refactored `smart_home`, `synth_shop`, and `office_management` to follow the latest v0.9.3 protocol patterns.

### Fixed
- **Silent API Failures**: Resolved issue where hallucinated parameters (like `status: "on"`) resulted in silent success without state change. The API now throws `400 Bad Request` with an actionable remedy.
- **Import Errors**: Fixed broken imports in all example files caused by the package refactoring.
- **Context Management**: Hard limit of 5000 characters applied to agent-facing result strings to prevent token exhaustion from large log files or tracebacks.

---
*Note: This version is stable and ready for agentic workflow benchmarking.*
