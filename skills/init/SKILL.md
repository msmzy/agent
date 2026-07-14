---
name: init
description: Initialize project documentation by scanning the codebase and generating a REPOPILOT.md file.
triggers:
  - /init
  - initialize project
  - setup repopilot
tags:
  - setup
  - documentation
  - onboarding
applicable_when: User wants to set up RepoPilot for a new project
not_applicable_when: Project already has REPOPILOT.md
---

# Init Skill

Scan the current project and generate a `REPOPILOT.md` file with:

1. **Project Overview**: Detect language, framework, and purpose from package files
2. **Directory Structure**: Map the top-level directory layout
3. **Key Files**: Identify entry points, config files, and important modules
4. **Build & Run**: Extract build/run commands from package.json, Makefile, pyproject.toml, etc.
5. **Conventions**: Note coding style, naming patterns, and test structure

Steps:
1. Use `glob` to find package files (package.json, pyproject.toml, Cargo.toml, go.mod, etc.)
2. Use `read_file` to examine key config files
3. Use `glob` to understand directory structure
4. Use `write_file` to create REPOPILOT.md with findings
