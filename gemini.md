# GEMINI.md

## Priority
These are Antigravity-specific rules. Also follow AGENTS.md and SPEC.md. If anything conflicts, this file wins.

## Agent workflow
- Use Planning mode. Before editing files for a phase, produce a task list and implementation plan, and wait for my approval.
- When a phase is finished, produce a short walkthrough: what changed, what was tested, what is left.
- Read SPEC.md and AGENTS.md at the start of every session. If the current phase is unclear, ask me.

## Terminal and safety
- Run pytest and ruff after every phase before reporting it done.
- Ask before any destructive command: rm -rf, git reset --hard, git push --force, or deleting branches.
- Do not push to GitHub. I will push after reviewing.
- Never rewrite or amend git history. A clean commit history is part of the assessment.

## Browser agent
- Use the browser only to check the Streamlit app on localhost, or to test the audit against the target URL I give you.
- Do not browse other sites or download anything.

## Gemini API usage
- Use the google-genai SDK. Read GEMINI_API_KEY from the environment and the model name from GEMINI_MODEL. Never hardcode either.
- Stay inside free-tier limits: send compact summaries of findings, cache LLM results per audit, and retry with backoff on rate-limit errors.
- Use the Pydantic model as the response schema for structured output.

## Style
- Keep explanations short and specific. Show a summary of each diff.
- Prefer simple, readable code over clever abstractions.