from elemm.base import BaseAIProtocolManager
from elemm.models import AIAction

def test_manifest_noise_reduction():
    manager = BaseAIProtocolManager(agent_welcome="Welcome")
    
    # Register a standard action
    manager.register_action(
        id="test_action",
        type="read",
        description="A test action",
        instructions="Use this to test noise reduction",
        method="POST",
        url="/api/test",
        groups=["test"],
        global_access=True,
        tags=["debug"],
        hidden=False
    )
    
    # Get manifest for LLM (default)
    manifest = manager.get_manifest()
    actions = manifest["actions"]
    
    print("LLM View Actions:")
    for action in actions:
        print(f"Keys: {list(action.keys())}")
        if "url" in action or "method" in action or "groups" in action:
            print("FAILURE: Noise fields found in LLM view!")
        else:
            print("SUCCESS: Noise fields removed.")

    # Get internal manifest
    internal_manifest = manager.get_manifest(group="_INTERNAL_ALL_")
    internal_actions = internal_manifest["actions"]
    print("\nInternal View Actions:")
    for action in internal_actions:
        # Pydantic model dump results in dict here
        keys = action.keys() if isinstance(action, dict) else action.__dict__.keys()
        print(f"Keys: {list(keys)}")
        if "url" in keys and "method" in keys:
             print("SUCCESS: Technical fields preserved in internal view.")
        else:
             print("FAILURE: Technical fields missing in internal view!")

if __name__ == "__main__":
    test_manifest_noise_reduction()
