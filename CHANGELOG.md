# Changelog

All notable changes to this project are documented here. The format is loosely
based on [Keep a Changelog](https://keepachangelog.com/), and the project aims
to follow semantic versioning.

## [Unreleased]

- Breaking: custom CodeAct error formatters must implement
  `format(error, code=None, *, line_offset=0, formatted_error="", max_error=None, tail_chars=None)`.
  Reduced legacy signatures are no longer supported.
- Initial public release of NVIDIA Object-Oriented Agents (NOOA).
- Security: MCP server configurations no longer expand host environment variables
  from `${VAR}` placeholders. Trusted caller code must resolve secrets and pass
  their values explicitly.
