# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-05-08

### Added
- **Initial Release of Elemm v2**: A robust, domain-agnostic protocol for autonomous agents.
- **Semantic Landmarks**: High-level tool grouping for efficient context management and discovery.
- **SmartRepair Engine**: Automated error recovery with actionable remedies for AI agents.
- **High-Performance Sequencing**: Execution of complex tool chains in a single LLM turn.
- **Variable Piping**: Seamless data flow between tools using `$alias.field` syntax.
- **Intelligent Type Mapping**: Automatic conversion of Python Pydantic models, Literals, and Enums to technical protocol schemas.
- **Safety Lock**: Mandatory `get_manifest` discovery phase to prevent blind tool execution.
- **Context Isolation**: Multi-landmark execution isolation using `ContextVar`.
- **Developer Experience**: New `@manager.landmark` decorator for simplified tool registration.
- **Solaris Gauntlet Benchmark**: Advanced head-to-head comparison suite with token and cost tracking for protocol validation.

### Changed
- **Migration to GPLv3**: Project is now licensed under the GNU General Public License v3.
- **Documentation Overhaul**: Full parity between source code and documentation.

---
*Initial stable release by Marc Stöcker.*
