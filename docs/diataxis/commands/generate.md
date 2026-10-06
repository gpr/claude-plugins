---
description: Generate Diataxis-compliant documentation for code, features, or modules
allowed-tools:
  - Bash
  - Write
  - Read
  - Glob
  - Grep
  - Task
  - AskUserQuestion
  - mcp__repomix__pack_codebase
  - mcp__repomix__grep_repomix_output
  - mcp__repomix__read_repomix_output
argument-hint: "[target] [type]"
---

# Generate Diataxis Documentation

Generate documentation following the Diataxis framework using Repomix for codebase analysis.

## Arguments
- `target`: File path, feature name, module, or directory to document (optional - will ask if not provided)
- `type`: Documentation type - `tutorial`, `howto`, `reference`, or `explanation` (optional - will recommend based on content)

## Instructions

1. **Determine the target**:
   - If no target provided, ask the user what to document
   - Accept file paths, feature names, module names, or directory paths

2. **Analyze the codebase**:
   - Use `@agent-diataxis:doc-analyzer` to explore the target code
   - The agent will use Repomix MCP tools (`pack_codebase`, `grep_repomix_output`)
   - Gather context about code structure, public APIs, and functionality

3. **Determine documentation type**:
   - If `type` argument provided, use that type
   - Otherwise, recommend based on what's being documented:
     - New feature / getting started → **Tutorial**
     - Specific task / integration → **How-to Guide**
     - API / CLI / Config options → **Reference**
     - Architecture / Design decisions → **Explanation**
   - Confirm with user if recommendation is unclear

4. **Generate documentation**:
   - Use `@agent-diataxis:doc-generator` with the analysis results and chosen type
   - The agent will create Diataxis-compliant content following type-specific templates
   - Ensure code examples are extracted from actual code

5. **Save documentation**:
   - Place in appropriate directory:
     - `docs/tutorials/` for tutorials
     - `docs/how-to/` for how-to guides
     - `docs/reference/` for reference docs
     - `docs/explanation/` for explanations
   - Use descriptive kebab-case filename
   - If docs structure doesn't exist, suggest running `/diataxis:init` first

6. **Report completion**:
   - Show file location
   - Summarize what was documented
   - Suggest review and any follow-up documentation needs

Reference the `diataxis-framework` skill for type-specific writing guidance.
