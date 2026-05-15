# Copyright (C) 2026 Marc Stöcker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import json
from fastapi import FastAPI, APIRouter, Body, Response, Query
from typing import Any, Dict, List, Optional, Union
from ..core.manager import AIProtocolManager

class FastAPIGateway:
    """Brücke zwischen AIProtocolManager und FastAPI."""
    
    def __init__(self, manager: AIProtocolManager):
        self.manager = manager

    def get_router(self) -> APIRouter:
        """Erstellt einen Router für die Discovery-Endpunkte."""
        router = APIRouter(prefix="/elemm")
        
        @router.get("/manifest", tags=["discovery"])
        async def get_manifest():
            return self.manager.get_manifest_dict()
            
        @router.get("/landmarks", tags=["discovery"])
        async def get_landmarks():
            # Vereinfachte Liste für Discovery
            return [
                {"id": l.id, "type": l.type, "description": l.description}
                for l in self.manager.landmarks.values()
            ]
            
        return router

    def bind_to_app(self, app: FastAPI):
        """Bindet die Protokoll-Endpunkte an eine FastAPI-Instanz."""
        self.app = app
        
        # Standardisierte Discovery auf Root-Ebene
        from fastapi import Response, Query
        # v1 Pattern: Agent Repair Handler
        from fastapi.exceptions import RequestValidationError
        from fastapi.responses import JSONResponse
        from fastapi import Request

        @self.app.exception_handler(RequestValidationError)
        async def elemm_validation_exception_handler(request: Request, exc: RequestValidationError):
            path_template = ""
            if "route" in request.scope:
                path_template = getattr(request.scope["route"], "path", "")
            
            method = request.method
            # Suche Landmark basierend auf Path (vereinfacht für v2)
            matched_landmark = None
            for lm in self.manager.landmarks.values():
                # Wir suchen hier nach Landmarks, die einen Handler haben
                if lm.handler:
                    # In v2 müssen wir eventuell die URL-Zuordnung noch besser tracken
                    # Für den Benchmark-Fall nehmen wir an, wir finden sie über die ID im Pfad oder Tags
                    pass
            
            errors = exc.errors()
            response_body = {
                "status": "error",
                "error_type": "validation_failed",
                "message": "Invalid tool call parameters.",
                "details": errors,
            }

            # Wenn wir die Landmark nicht eindeutig finden, geben wir einen allgemeinen Tipp
            response_body["remedy"] = "Verify your parameter names and types against the manifest. Use 'inspect_landmark(id)' for technical details."
            response_body["instruction"] = "Fix the parameters listed in 'details' and retry."
            
            return JSONResponse(status_code=422, content=response_body)

        @self.app.get("/.well-known/elemm-manifest.md", tags=["discovery"], include_in_schema=False)
        @self.app.get("/.well-known/elemm-inspect.md", tags=["discovery"], include_in_schema=False)
        async def well_known_manifest(
            response: Response, 
            landmark_id: Optional[str] = Query(None),
            full: bool = False,
            technical: bool = False,
            output_format: str = Query("markdown", alias="format"),
            limit: Optional[int] = Query(None),
            offset: Optional[int] = Query(0)
        ):
            """Manifest-Discovery im v1-Format."""
            response.headers["Link"] = '</.well-known/elemm-manifest.md>; rel="elemm-manifest"'
            
            # Default-Limit für Browser/Public-Discovery, falls nicht vom Gateway gesetzt
            ctx_limit = limit if limit is not None else 5000
            
            # Auto-switch to technical if it's an inspect call
            is_inspect = landmark_id is not None
            
            # Wenn landmark_id übergeben wird, zeigen wir Details (FOCUS)
            if landmark_id:
                # Wir konvertieren zu Liste und splitten Kommas
                if isinstance(landmark_id, str):
                    query_ids = [id.strip().lower() for id in landmark_id.split(",")]
                else:
                    query_ids = [id.lower() for id in landmark_id]
                
                # Case-insensitive Lookup: Resolve to original stored IDs
                lms_to_query = []
                all_lms_lower = {lid.lower(): lid for lid in self.manager.landmarks.keys()}
                for qid in query_ids:
                    original_id = all_lms_lower.get(qid)
                    if original_id:
                        lms_to_query.append(original_id)
                
                # If limit is small (e.g. < 500), treat it as an item limit (max_landmarks)
                # otherwise treat as character limit.
                p_kwargs = {"offset": offset}
                if offset is not None: p_kwargs["offset"] = offset
                if limit is not None:
                    if limit < 500:
                        p_kwargs["max_landmarks"] = limit
                    else:
                        p_kwargs["limit"] = limit

                p_kwargs["output_format"] = output_format
                manifest_md = self.manager.get_manifest(lms_to_query, technical=technical, **p_kwargs)
            else:
                # Standard-Manifest mit v1-Logik (Summary)
                p_kwargs = {"technical": technical or full, "offset": offset}
                if limit is not None:
                    if limit < 500:
                        p_kwargs["max_landmarks"] = limit
                    else:
                        p_kwargs["limit"] = limit
                else:
                    p_kwargs["limit"] = limit if limit is not None else ctx_limit
                
                p_kwargs["output_format"] = output_format
                manifest_md = self.manager.get_manifest(**p_kwargs)
            
            if output_format == "json":
                # Ensure we have valid JSON to parse
                if not manifest_md: return JSONResponse(content=[])
                try:
                    return JSONResponse(content=json.loads(manifest_md))
                except json.JSONDecodeError:
                    return JSONResponse(status_code=500, content={"error": "Presenter failed to generate valid JSON", "raw": manifest_md})
            
            return Response(content=manifest_md, media_type="text/markdown")

        @self.app.post("/.well-known/elemm/execute", tags=["execution"], include_in_schema=False)
        async def well_known_execute(
            request: Request,
            body: Dict[str, Any] = Body(...)
        ):
            """
            Zentraler Execution-Endpoint für Elemm-Clients (Broker, AnythingLLM, etc.).
            Unterstützt Einzel-Calls und Sequenzen.
            """
            # 1. Check for Sequence
            if "actions" in body:
                actions = body["actions"]
                results = await self.manager.sequencer.run(actions, self.manager.global_context)
                return results
            
            # 2. Check for Single Action
            action_id = body.get("action_id") or body.get("action")
            parameters = body.get("parameters", {})
            
            if not action_id:
                return JSONResponse(
                    status_code=400, 
                    content={"status": "error", "message": "Missing 'action_id' or 'actions' in request body."}
                )

            # Resolve piping if any (global context)
            resolved_params, err = self.manager.sequencer.resolve_all(parameters, self.manager.global_context)
            if err:
                return JSONResponse(status_code=400, content={"status": "error", "message": f"Piping failed: {err}"})

            result = await self.manager.call_action(action_id, resolved_params)
            return result

        @self.app.get("/.well-known/elemm/search")
        async def search_landmarks(query: str, limit: int = None, offset: int = 0, technical: bool = False, output_format: str = Query("markdown", alias="format")):
            """Suche nach Landmarks."""
            p_kwargs = {"offset": offset, "technical": technical, "output_format": output_format}
            if limit is not None:
                if limit < 500: p_kwargs["max_landmarks"] = limit
                else: p_kwargs["limit"] = limit
            else:
                p_kwargs["limit"] = 10000 # Default character budget for search
                
            res = self.manager.search_landmarks(query, **p_kwargs)
            if output_format == "json":
                if not res: return JSONResponse(content=[])
                try:
                    return JSONResponse(content=json.loads(res))
                except json.JSONDecodeError:
                    return JSONResponse(status_code=500, content={"error": "Search failed to generate valid JSON", "raw": res})
            return Response(content=res, media_type="text/markdown")

        # Technisches Interface via Router
        router = self.get_router()
        app.include_router(router)
