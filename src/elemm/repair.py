import json
from typing import Any, Dict
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

async def agent_repair_handler(manager, request: Request, exc: RequestValidationError):
    """
    Enriches validation errors with landmark 'remedy' instructions to help LLMs self-correct.
    
    Args:
        manager: The FastAPIProtocolManager instance.
        request: The FastAPI request object.
        exc: The validation error.
    """
    path_template = ""
    if "route" in request.scope:
        path_template = getattr(request.scope["route"], "path", "")
    
    method = request.method
    matched_action = None
    for action in manager.actions:
        if action.url == path_template and action.method == method:
            matched_action = action
            break
    
    errors = exc.errors()
    if not matched_action:
        # Fallback to standard FastAPI format for non-landmark routes
        return JSONResponse(status_code=422, content={"detail": errors})

    response_body = {
        "status": "error",
        "error_type": "validation_failed",
        "managed_by": "elemm",
        "message": "The AI Agent sent an invalid request according to the landmark protocol.",
        "details": errors,
    }

    if matched_action.remedy:
        response_body["remedy"] = matched_action.remedy
    else:
        # Dynamic guidance based on groups
        target_group = matched_action.groups[0] if matched_action.groups else "root"
        response_body["remedy"] = f"CRITICAL: Parameter mismatch for '{matched_action.id}'. Please call 'inspect_landmark(\"{target_group}\")' to verify the exact parameter names and types required for this tool."
    
    if matched_action.instructions:
        response_body["instruction"] = matched_action.instructions
    else:
        response_body["instruction"] = "Follow the 'remedy' above to fix your parameters and try again."
    
    # Noise Detection Heuristic
    try:
        received_params = []
        if method in ["POST", "PUT", "PATCH"]:
            body = await request.json()
            if isinstance(body, dict):
                received_params = list(body.keys())
        
        allowed_params = []
        if matched_action.parameters:
            allowed_params += [p.name for p in matched_action.parameters]
        if matched_action.payload:
            if isinstance(matched_action.payload, list):
                allowed_params += [p.name for p in matched_action.payload]
            elif isinstance(matched_action.payload, dict):
                allowed_params += list(matched_action.payload.keys())
        
        spurious = [p for p in received_params if p not in allowed_params]
        if spurious:
            response_body["noise_warning"] = f"Action does not support these parameters: {spurious}. Stick to the manifest."
    except Exception:
        pass

    return JSONResponse(status_code=422, content=response_body)
