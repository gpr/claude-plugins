---
description: Update existing documentation based on code changes
allowed-tools:
  - Bash
  - Write
  - Edit
  - Read
  - Glob
  - Grep
  - Task
  - AskUserQuestion
  - mcp__repomix__pack_codebase
  - mcp__repomix__grep_repomix_output
  - mcp__repomix__read_repomix_output
argument-hint: "[doc] [scope]"
---

# Update Existing Documentation

Update documentation to reflect code changes while preserving Diataxis structure and type compliance.

## Arguments
- `doc`: Path to specific documentation file to update (optional)
- `scope`: What changed - file path, feature name, or "all" for full sync (optional)

## Instructions

1. **Identify what needs updating**:
   - If `doc` provided: focus on that specific document
   - If `scope` provided: find all documentation related to that scope
   - If neither provided: ask user what changed, or check recent git changes with `git diff --name-only HEAD~5`

2. **Analyze current code state**:
   - Use `@agent-diataxis:doc-analyzer` to understand current code
   - Focus on the areas that have changed
   - Identify what information in docs may be outdated

3. **Compare against existing documentation**:
   - Read the target documentation file(s)
   - Identify discrepancies between code and docs:
     - Changed function signatures or parameters
     - New or removed features
     - Updated configuration options
     - Modified behavior or outputs

4. **Preserve documentation structure**:
   - **Critical**: Maintain the existing Diataxis type - do not change a tutorial into a reference
   - Keep the document's voice and style consistent
   - Update only factual content that changed
   - Do not add new sections unless necessary

5. **Update by documentation type**:
   - **Tutorials**: Update steps, expected outputs, screenshots references
   - **How-to Guides**: Update procedures, prerequisites, troubleshooting
   - **Reference**: Update specifications, options, parameters, defaults
   - **Explanation**: Update context only if architecture fundamentally changed

6. **Validate updates**:
   - Ensure document still follows its Diataxis type guidelines
   - Check that code examples still work
   - Verify internal links aren't broken
   - Confirm formatting is consistent

7. **Report changes**:
   - Summarize what was updated (use diff-style if helpful)
   - Highlight any sections that need manual review
   - Suggest additional documentation updates if related docs exist
   - Warn if the update seems to require a type change (this should be rare)

Reference the `diataxis-framework` skill to ensure updates maintain type compliance.
