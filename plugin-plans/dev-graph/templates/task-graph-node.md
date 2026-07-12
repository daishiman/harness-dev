# Task graph node

## Identity and classification

- Node ID: `<graph_node_id>`
- Artifact kind/subtypes: `<kind>/<subtypes>`
- Project/domain/tags/status: <values>
- Canonical file: `<file_path>`

## Goal and value

- Goal state: <observable state>
- User/system value: <value>

## Graph relations

- `depends_on`: <node ids that must complete first>
- `blocks`: <derived downstream ids>
- `related_to`: <non-ordering references>
- `implements`: <spec/architecture ids>
- `produces` / `consumes`: <artifacts>

## Scheduling

- Priority: <value and reason>
- `touches`: <resource scopes>
- Exclusive resources: <keys>
- Ready condition: <dependency/status/readiness expression>
- Parallel group constraints: <rules>

## Completion contract

- Acceptance: <observable result>
- Verification: <command/evidence>
- Handoff route: <builder or owner>

