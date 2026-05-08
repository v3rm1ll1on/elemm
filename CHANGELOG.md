# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-05-08

### Added
- **Pydantic Smart Unboxing**: Automatic expansion of single Pydantic model arguments into individual tool parameters for improved agent interaction.
- **Hierarchical Remedies**: Implemented remedy inheritance where tools can automatically use global remedies defined at the landmark level.
- **Declarative YAML Reference**: Added comprehensive schema documentation for `landmarks.yaml` configuration.
- **Extended Registry Support**: Added support for YAML aliases like `remedy_global` and explicit `configure_landmark` programmatic API.

### Changed
- **Branding Update**: Rebranded the protocol to **Elemm: The Landmark Manifest Protocol**.
- **Documentation Overhaul**: Professionalized all documentation files and improved layout consistency.
- **API Refinement**: Introduced `ElemmGateway` as the primary high-level API and added **Auto-Prefixing** for landmark actions.

## [1.0.0] - 2026-05-08

### Added
- **Initial Release**: Landmark Manifest Protocol for autonomous agents.
- **Semantic Landmarks**: Logical tool grouping for efficient context discovery.
- **SmartRepair Engine**: Automated agent recovery with actionable remedies.
- **High-Performance Sequencing**: Execution of multi-step tool chains in a single turn.
- **Variable Piping**: Server-side data flow between actions via `$alias.field`.
- **Intelligent Type Mapping**: Automatic conversion of Pydantic models and Python types to protocol schemas.
- **Solaris Gauntlet Benchmark**: Comparative suite for performance and cost validation.

### Changed
- **License**: Project released under the GPLv3 License.

---
*Initial stable release by Marc Stöcker.*
