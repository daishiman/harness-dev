---
name: nested-probe
description: Native foreground nested Agent transport probe.
context: fork
allowed-tools:
  - Agent
  - Task
---
Invoke exactly one Agent of subagent_type general-purpose with prompt "Return only FG_NESTED_MARKER; do not use tools or access files". Wait for its real final response. Return that response only. If Agent is unavailable report UNAVAILABLE and do not invent a response.
