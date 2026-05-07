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
        async def well_known_manifest(
            response: Response, 
            landmark_id: Optional[Union[str, List[str]]] = Query(None),
            technical: bool = Query(False),
            full: bool = Query(False)
        ):
            """Manifest-Discovery im v1-Format."""
            response.headers["Link"] = '</.well-known/elemm-manifest.md>; rel="elemm-manifest"'
            
            # Wenn landmark_id übergeben wird, zeigen wir Details (FOCUS)
            if landmark_id:
                # Wir konvertieren zu Liste falls nötig
                ids = [landmark_id] if isinstance(landmark_id, str) else landmark_id
                lms = [self.manager.landmarks[lid] for lid in ids if lid in self.manager.landmarks]
                manifest_md = self.manager.presenter.present_manifest(lms, full=True, skip_header=False, technical=technical)
            else:
                # Standard-Manifest mit v1-Logik (Summary)
                manifest_md = self.manager.get_manifest_md(technical=technical)
            
            return Response(content=manifest_md, media_type="text/markdown")

        @self.app.get("/.well-known/elemm-inspect.md", tags=["discovery"], include_in_schema=False)
        async def well_known_inspect(response: Response, landmark_id: Optional[Union[str, List[str]]] = Query(None)):
            """Alias für manifest detail view."""
            return await well_known_manifest(response, landmark_id=landmark_id)

        @self.app.get("/.well-known/elemm", tags=["discovery"], include_in_schema=False)
        async def well_known_legacy(response: Response):
            """Legacy redirect/alias for v2 discovery."""
            return await well_known_manifest(response)

        # Technisches Interface via Router
        router = self.get_router()
        app.include_router(router)
