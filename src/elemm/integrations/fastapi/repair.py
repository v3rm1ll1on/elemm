# This file is part of Elemm.
#
# Elemm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Elemm is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Elemm.  If not, see <https://www.gnu.org/licenses/>.

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
        # Guidance based on landmark groups and parameters
        target_group = matched_action.groups[0] if matched_action.groups else "root"
        
        response_body["remedy"] = f"Parameter validation failed for '{matched_action.id}'."
        
        if matched_action.groups:
            groups_str = ", ".join(matched_action.groups)
            response_body["remedy"] += f" Note: This tool belongs to [{groups_str}]. Verify your parameters against the manifest definitions for these landmarks."
        else:
            response_body["remedy"] += f" Please call 'inspect_landmark(\"{target_group}\")' to verify the required parameter names and types."
    
    if matched_action.instructions:
        response_body["instruction"] = matched_action.instructions
    else:
        response_body["instruction"] = "Follow the 'remedy' above to fix your parameters and try again."
    
    # Noise Detection Heuristic
    try:
        received_params = []
        if method in ["POST", "PUT", "PATCH"]:
            # Use body() to safely access raw content (caches automatically in Starlette)
            raw_body = await request.body()
            if raw_body:
                body = json.loads(raw_body)
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
