---
description: Initialize a Diataxis documentation structure in the project
allowed-tools:
  - Bash
  - Write
  - Read
  - Glob
  - AskUserQuestion
---

# Initialize Diataxis Documentation Structure

Create a documentation structure following the Diataxis framework with directories for tutorials, how-to guides, references, and explanations.

## Instructions

1. **Ask the user about their project**:
   - Project name and brief purpose
   - Primary audience (developers, end-users, operators)
   - Existing documentation location (if any)
   - Preferred documentation directory (default: `docs/`)

2. **Check for existing documentation**:
   - Use Glob to find existing markdown files
   - If docs exist, ask if user wants to reorganize or start fresh

3. **Create the directory structure**:
   ```
   docs/
   ├── tutorials/
   ├── how-to/
   ├── reference/
   ├── explanation/
   └── index.md
   ```

4. **Generate index.md** with:
   - Project documentation title
   - Brief description
   - Links to each section with explanations of what belongs there
   - Quick start pointer to tutorials

5. **Generate section README files** (`tutorials/index.md`, etc.) explaining:
   - What belongs in this section
   - How to write content for this section
   - Link to the Diataxis framework skill for detailed guidance

6. **Report completion** with:
   - Summary of created structure
   - Recommended next steps (suggest `/diataxis:generate` or `/diataxis:audit`)

Reference the `diataxis-framework` skill for detailed guidance on each documentation type.
