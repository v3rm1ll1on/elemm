# Elemm v2: Gateway Auth Roadmap

## 🚀 High Priority: Gateway-Aware Manifest Hints
- [ ] **Dynamic Token Mapping:**
    - Implement a `gateway_hints` section in `landmarks.yaml` to specify where authentication tokens are located in API responses.
    - Update `Presenter` to include these hints in a hidden block when `?technical=true` is requested.
    - Modify `ElemmGateway` (Broker) to parse and then strip these hints before presenting the manifest to the Agent.
    - Support mapping custom keys (e.g., `token`, `session_id`) to the `Authorization` header automatically.
