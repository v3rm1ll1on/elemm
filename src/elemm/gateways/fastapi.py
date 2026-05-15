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
            technical: bool = Query(False),
            full: bool = Query(False),
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
                
                # Case-insensitive Lookup
                lms = []
                all_lms_lower = {lid.lower(): lm for lid, lm in self.manager.landmarks.items()}
                
                # If limit is small (e.g. < 500), treat it as an item limit (max_landmarks)
                # otherwise treat as character limit.
                p_kwargs = {"offset": offset}
                if offset is not None: p_kwargs["offset"] = offset
                if limit is not None:
                    if limit < 500:
                        p_kwargs["max_landmarks"] = limit
                    else:
                        p_kwargs["limit"] = limit

                manifest_md = self.manager.get_manifest(query_ids, technical=technical, **p_kwargs)
            else:
                # Standard-Manifest mit v1-Logik (Summary)
                p_kwargs = {"technical": technical or full, "offset": offset}
                if limit is not None:
                    if limit < 500:
                        p_kwargs["max_landmarks"] = limit
                    else:
                        p_kwargs["limit"] = limit
                else:
                    p_kwargs["limit"] = ctx_limit
                    
                manifest_md = self.manager.get_manifest(**p_kwargs)
            
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

        # Technisches Interface via Router
        router = self.get_router()
        app.include_router(router)
