---
description: Audit existing documentation against Diataxis standards
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - Task
  - mcp__repomix__pack_codebase
  - mcp__repomix__grep_repomix_output
  - mcp__repomix__read_repomix_output
argument-hint: "[path]"
---

# Audit Documentation Against Diataxis Standards

Analyze existing documentation and report on Diataxis compliance, coverage gaps, and recommendations.

## Arguments
- `path`: Documentation directory to audit (default: `docs/`)

## Instructions

1. **Discover existing documentation**:
   - Use Glob to find all markdown files in the docs directory
   - Identify existing structure (subdirectories, README files)
   - Count documents by location

2. **Analyze documentation**:
   - Use `@agent-diataxis:doc-analyzer` to examine each document
   - Classify each document by Diataxis type based on actual content (not location)
   - Identify documents that mix types inappropriately

3. **Compare against codebase** (optional but recommended):
   - Use Repomix to understand the codebase
   - Identify public APIs, features, and configs
   - Compare against what's documented

4. **Generate audit report** with these sections:

   **Coverage Summary**:
   | Type | Count | Examples |
   |------|-------|----------|
   | Tutorials | N | ... |
   | How-to Guides | N | ... |
   | Reference | N | ... |
   | Explanation | N | ... |
   | Unclassified | N | ... |

   **Classification Report**:
   | Document | Current Location | Detected Type | Recommended Location | Issues |
   |----------|-----------------|---------------|---------------------|--------|

   **Quality Issues**:
   - Documents mixing multiple Diataxis types
   - Tutorials without step-by-step structure
   - How-to guides with excessive explanation
   - Reference docs with instructional content
   - Explanations without context/connections

   **Coverage Gaps**:
   - Undocumented public APIs
   - Missing getting-started tutorial
   - Features without how-to guides

   **Recommendations** (prioritized):
   1. High priority items to address
   2. Suggested reorganization
   3. New documentation to create

5. **Offer next steps**:
   - If structure missing: suggest `/diataxis:init`
   - If gaps found: offer to generate specific documentation with `/diataxis:generate`
   - If reorganization needed: provide specific file move suggestions

Reference the `diataxis-framework` skill to evaluate documents against type criteria.
