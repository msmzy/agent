---
name: review
description: Review code changes (git diff or specific files) for bugs, security issues, and style.
triggers:
  - /review
  - review code
  - code review
  - review changes
tags:
  - review
  - quality
  - security
applicable_when: User wants feedback on code changes or a pull request
not_applicable_when: User is asking to write new code
---

# Review Skill

Perform a structured code review:

1. **Get Changes**: Run `git diff` or `git diff --staged` to see current changes
2. **Analyze**: Check each changed file for:
   - Bugs and logic errors
   - Security vulnerabilities (OWASP top 10)
   - Performance issues
   - Style inconsistencies
   - Missing error handling at system boundaries
3. **Report**: Provide findings organized by severity (critical → minor)

Review checklist:
- [ ] No hardcoded secrets or credentials
- [ ] Input validation at system boundaries
- [ ] No SQL injection, XSS, or command injection
- [ ] Error handling is appropriate (not excessive)
- [ ] No unnecessary complexity or premature abstraction
- [ ] Tests cover the changes
