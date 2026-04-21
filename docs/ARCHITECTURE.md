# Elemm Architecture: Hierarchical Navigation and Scalability

Elemm transforms a flat API structure into a navigable world of landmarks. This allows AI agents to access extremely large toolsets without overloading the context window.

## 1. Automated Navigation (Signposts)

A core feature of Elemm is the automatic generation of navigation points. Developers do not need to write manual tools for switching between modules.

### How it works
Elemm analyzes the `openapi_tags` of a FastAPI application. If a route has a tag defined in the application's metadata, Elemm automatically generates a navigation landmark for that group.

- **ID Generation**: Groups automatically receive the prefix `explore_{tag_id}`.
- **Sanitization**: Special characters in tags are automatically cleaned (e.g., `User & Admin` becomes `explore_user_and_admin`).
- **Instructions**: Descriptions from the FastAPI tags serve as the primary orientation guide for the agent.

## 2. Hybrid Mode (Auto-Flattening)

Elemm adapts to the size of the API. In version 0.6.0, a hybrid mode was introduced:
- **Flat View**: If an API has fewer than 10 landmarks and uses no explicit group structure, Elemm removes the filtering. The agent sees all tools at once.
- **Hierarchical View**: As soon as the API grows or groups (tags) are defined, the protocol switches to structured mode. This prevents the "navigation tax" (unnecessary steps) for very simple APIs while maintaining scalability for complex systems.

## 3. Token Hygiene and Best Practices

The hierarchical structure drastically reduces token consumption because only relevant tools are in context per step.

### Global Access
Tools with `global_access=True` are visible in every module.
**Recommendation**: Use this attribute sparingly for absolutely essential tools (e.g., `system_status` or `help`). Too many global tools lead to context noise and diminish the advantage of the hierarchy.

## 4. Discovery Lifecycle

1. **Initialization**: `bind_to_app` recognizes landmarks from tags and explicit registrations.
2. **Root Level**: The agent initially sees only navigation points and global tools.
3. **Navigation**: The agent uses the `navigate` tool to enter a module.
4. **Focusing**: The bridge now delivers a filtered manifest containing only the tools of the selected module.
5. **Efficiency**: In practice, the size of the tool catalog per step is often reduced by a factor of 10 to 50.
