---
name: explain
description: Explain how a specific piece of code, module, or system works.
triggers:
  - /explain
  - explain this
  - how does this work
  - what does this do
tags:
  - explain
  - understanding
  - learning
applicable_when: User wants to understand existing code
not_applicable_when: User wants to modify or write code
---

# Explain Skill

Provide a clear explanation of code:

1. **Locate**: Find the relevant code using `grep` and `glob`
2. **Read**: Use `read_file` to examine the code
3. **Trace**: Follow the execution flow through function calls
4. **Explain**: Provide a layered explanation:
   - **One-liner**: What it does in one sentence
   - **How it works**: Step-by-step walkthrough
   - **Key decisions**: Why it's designed this way
   - **Connections**: How it relates to other parts of the codebase

Tailor depth to the user's expertise level. Use analogies for complex concepts.
