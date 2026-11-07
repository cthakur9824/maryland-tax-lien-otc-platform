# Workspace Skills Directory

Place your custom skills in this directory.

## Skill Folder Structure
Each skill should reside in its own folder with a `SKILL.md` file:

```text
.agents/skills/
├── your-skill-name/
│   ├── SKILL.md          <- Required: Main instructions with frontmatter
│   ├── scripts/          <- Optional: Helper scripts
│   ├── references/       <- Optional: Reference documentation
│   └── examples/         <- Optional: Example inputs/outputs
```

## Example `SKILL.md` Template
```markdown
---
name: your-skill-name
description: >-
  Describe what this skill does and when the agent should activate it.
---

# Your Skill Name

Step-by-step instructions for the agent to follow...
```
