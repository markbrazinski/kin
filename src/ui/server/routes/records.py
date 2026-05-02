"""GET /intake/records — list all persisted intake records."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import structlog

log = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/intake/records")
async def list_records(request: Request) -> JSONResponse:
    storage = request.app.state.storage
    if storage is None:
        return JSONResponse({"records": []})
    records = storage.list_intake_records()
    log.info("intake_records_listed", count=len(records))
    return JSONResponse({
        "records": [r.model_dump(mode="json") for r in records]
    })
