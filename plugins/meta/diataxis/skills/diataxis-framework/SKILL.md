---
description: |
  Provides comprehensive knowledge about the Diataxis documentation framework.
  Use this skill when users discuss documentation structure, documentation types,
  ask about organizing docs, need to understand the difference between tutorials
  and how-to guides, want best practices for technical documentation, or mention
  "diataxis", "documentation architecture", or "docs organization".
---

# Diataxis Documentation Framework

The Diataxis framework organizes documentation into four distinct types based on two axes:
- **Practical vs. Theoretical** (action-oriented vs. knowledge-oriented)
- **Learning vs. Working** (acquisition vs. application)

## The Four Documentation Types

### 1. Tutorials (Learning-Oriented)

**Purpose**: Help beginners learn through guided, hands-on experiences.

**Characteristics**:
- Learning-oriented lessons that build skills progressively
- Step-by-step instructions with guaranteed, visible results
- Use first-person plural ("we") to guide alongside the learner
- Show the end goal upfront so learners know what they're building
- Deliver visible results after every step to maintain momentum
- Minimize explanation, maximize doing
- Require perfect reliability - every step must work

**Best Practices**:
- Trust learners to acquire understanding through doing
- Ruthlessly minimize abstraction and theory
- Permit repetition to build confidence
- Avoid presenting alternatives that distract from the learning path
- Test tutorials exhaustively - broken tutorials destroy trust

**Signals in existing docs**:
- "Getting started", "First", "Learn", "Introduction to"
- Step-by-step numbered instructions
- Progressive skill building
- Hands-on exercises with expected outputs

**Template structure**:
```markdown
# [Action-oriented title, e.g., "Build Your First API"]

In this tutorial, you will learn to [specific outcome].

## What you'll build
[Screenshot, diagram, or description of end result]

## Prerequisites
- [Minimal list - link to installation docs]

## Steps

### Step 1: [Action verb]
[Brief instruction]
[Code block with exactly what to type]
You should see: [Expected output]

### Step 2: [Action verb]
...

## What you learned
[Summary of skills acquired]

## Next steps
[Links to related tutorials or how-to guides]
```

### 2. How-to Guides (Task-Oriented)

**Purpose**: Guide users through specific real-world tasks they want to accomplish.

**Characteristics**:
- Goal-oriented directions for achieving specific outcomes
- Assume user already knows what they want to achieve
- Action-focused with no teaching or explanation
- Address real human needs and practical problems
- Adaptable to user's specific circumstances

**Best Practices**:
- Write from user needs perspective, not product features
- Maintain workflow flow - don't break concentration
- Use conditional imperatives: "If you want X, do Y"
- Link to reference docs for parameter details
- Name clearly: "How to [accomplish specific task]"
- Keep focused on one task per guide

**Signals in existing docs**:
- "How to" in title
- Task-focused procedures
- Assumes prior knowledge
- Goal-oriented steps without explanation

**Template structure**:
```markdown
# How to [Accomplish Specific Task]

This guide shows you how to [goal].

## Prerequisites
- [What user needs before starting]

## Steps

1. [First action]
   [Code or command]

2. [Second action]
   If you need [variation], [alternative instruction].

3. [Continue until goal achieved]

## Verification
[How to confirm success]

## Troubleshooting
- **[Common issue]**: [Solution]

## Related
- [Link to related how-to guides]
- [Link to reference for details]
```

### 3. Reference (Information-Oriented)

**Purpose**: Provide authoritative technical descriptions of the product.

**Characteristics**:
- Mirror the structure of the product itself
- Austere, neutral, objective tone
- State facts without instruction or opinion
- Standardized, consistent patterns throughout
- Wholly authoritative - the single source of truth

**Best Practices**:
- List all commands, options, operations, features
- Include warnings, constraints, and edge cases
- Provide illustrative examples for each item
- Never mix with instructional content
- Avoid marketing language or subjective opinions
- Use consistent formatting for all entries

**Signals in existing docs**:
- API documentation
- Parameter/option lists
- Technical specifications
- Neutral, factual tone
- Tables of options/parameters

**Template structure**:
```markdown
# [Component/API/Feature Name]

[One-line factual description]

## Overview
[Brief factual summary of what this is]

## [Options/Parameters/Methods]

### `option_name`
- **Type**: `string`
- **Default**: `"value"`
- **Required**: No

Description of what this option does.

**Example**:
[Usage example code]

## [Additional sections as needed]

## See also
- [Related reference pages]
```

### 4. Explanation (Understanding-Oriented)

**Purpose**: Deepen understanding through context, connections, and background.

**Characteristics**:
- Broad, high-level perspective on topics
- Answers "Can you tell me about...?" questions
- Consumable away from product use (reading material)
- Embraces multiple perspectives and trade-offs
- Discusses design decisions and alternatives

**Best Practices**:
- Make connections between concepts
- Provide historical context and design rationale
- Acknowledge alternatives and different opinions
- Use a guiding "why" question as the thread
- Titles allow implicit "about" prefix ("Understanding X" = "About X")
- Don't include step-by-step instructions

**Signals in existing docs**:
- "Understanding", "About", "Why", "Background"
- Conceptual discussion without steps
- Historical context
- Multiple perspectives or trade-offs

**Template structure**:
```markdown
# Understanding [Topic]

## Overview
[High-level introduction to the topic]

## Background
[Historical context, why this exists, problem it solves]

## How it works
[Conceptual explanation - not step-by-step]

## Design decisions
[Why it was built this way, trade-offs considered]

## Comparison with alternatives
[How this approach differs from others]

## Further reading
- [Links to deeper resources]
```

## Choosing the Right Type

| User Need | Documentation Type | Example Title |
|-----------|-------------------|---------------|
| "I want to learn" | Tutorial | "Build Your First REST API" |
| "I want to accomplish X" | How-to Guide | "How to Deploy to Production" |
| "I want to look up Y" | Reference | "CLI Command Reference" |
| "I want to understand Z" | Explanation | "Understanding Authentication" |

**Decision questions**:
1. Is the reader learning or already competent? → Learning = Tutorial, Competent = How-to
2. Is this about doing or understanding? → Doing = Tutorial/How-to, Understanding = Explanation/Reference
3. Does the reader have a specific goal? → Yes = How-to, No = Tutorial or Explanation
4. Is this factual lookup or conceptual? → Factual = Reference, Conceptual = Explanation

## Recommended Directory Structure

```
docs/
├── tutorials/           # Learning-oriented
│   ├── getting-started.md
│   ├── first-project.md
│   └── index.md
├── how-to/              # Task-oriented
│   ├── configure-auth.md
│   ├── deploy-production.md
│   └── index.md
├── reference/           # Information-oriented
│   ├── api/
│   ├── cli/
│   ├── config/
│   └── index.md
├── explanation/         # Understanding-oriented
│   ├── architecture.md
│   ├── design-decisions.md
│   └── index.md
└── index.md             # Documentation home
```

## Common Anti-Patterns

**Mixed-type documents** (most common issue):
- Tutorial that stops to explain concepts at length → Split into tutorial + explanation
- How-to guide that teaches basics first → Remove teaching, link to tutorial
- Reference with "how to use" sections → Move to how-to guide
- Explanation with step-by-step instructions → Split into explanation + how-to

**Wrong type for content**:
- Getting started guide written as reference → Rewrite as tutorial
- Conceptual overview with commands to run → Split appropriately
- FAQ that's really a how-to collection → Reorganize as how-to guides

**Signs of type confusion**:
- Document keeps switching between "you will learn" and "to accomplish X"
- Mix of imperative commands and explanatory paragraphs
- Reference docs with opinions about best practices
- Tutorials that assume knowledge not yet taught
