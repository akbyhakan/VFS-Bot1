"""Dashboard and frontend serving routes for VFS-Bot web application."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Initialize templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter(tags=["dashboard"])


@router.get("/errors.html", response_class=HTMLResponse)
async def errors_dashboard(request: Request):
    """
    Render errors dashboard page.

    Args:
        request: FastAPI request object

    Returns:
        HTML response with errors dashboard template
    """
    return templates.TemplateResponse(
        "errors.html", {"request": request, "title": "Error Dashboard - VFS Bot"}
    )


# Catch-all route for React SPA - MUST be registered last in main app!
async def serve_react_app(request: Request, full_path: str = ""):
    """
    Serve React SPA for all non-API routes with CSP nonce injection.

    This handles client-side routing by serving index.html for all routes
    that don't start with /api, /ws, /health, /metrics, or /static.

    Args:
        request: FastAPI request object
        full_path: Requested path

    Returns:
        HTML response with React app and CSP nonce injected
    """
    # Skip API routes, WebSocket, health checks, and static files
    if full_path.startswith(("api/", "ws", "health", "metrics", "static/", "assets/")):
        raise HTTPException(status_code=404, detail="Not found")

    # Serve the React app
    dist_dir = Path(__file__).parent.parent / "static" / "dist"
    index_file = dist_dir / "index.html"

    if index_file.exists():
        html_content = index_file.read_text(encoding="utf-8")
        return HTMLResponse(content=html_content, media_type="text/html")
    else:
        raise HTTPException(
            status_code=503, detail="Frontend not built. Run 'cd frontend && npm run build'"
        )
