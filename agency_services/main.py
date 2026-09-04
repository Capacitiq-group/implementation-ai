"""
Standalone FastAPI app for this repo — implements exactly the two
endpoints from portal-integration-brief.md §8, corrected to key on
agency_client_service_id per ARCHITECTURE.md §3/§4 (onboarding is
per-service, not per-client). Run with:
    uvicorn main:app --reload
"""

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException

from .config import settings
from .integrations.pocketbase_client import pocketbase
from .models import OnboardingStatus
from .orchestrator import run_implementation

app = FastAPI(title="Synkra Implementation AI Employee")


def _verify_admin_panel(x_internal_api_key: str | None) -> None:
    if not settings.admin_panel_internal_api_key or x_internal_api_key != settings.admin_panel_internal_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing internal API key")


@app.post("/implementation/trigger")
async def trigger(
    body: dict,
    background_tasks: BackgroundTasks,
    x_internal_api_key: str | None = Header(default=None),
):
    _verify_admin_panel(x_internal_api_key)
    agency_client_service_id = body.get("agency_client_service_id")
    if not agency_client_service_id:
        raise HTTPException(status_code=400, detail="agency_client_service_id is required")

    service_record = await pocketbase.get_record(
        "agency_client_services", f"id='{agency_client_service_id}'"
    )
    if not service_record:
        raise HTTPException(status_code=404, detail="agency_client_services record not found")
    if service_record.get("onboarding_status") != OnboardingStatus.ONBOARDING_NOTES_READY:
        raise HTTPException(
            status_code=409,
            detail=f"onboarding_status is {service_record.get('onboarding_status')!r}, expected "
                   f"{OnboardingStatus.ONBOARDING_NOTES_READY!r}",
        )

    await pocketbase.update_record(
        "agency_client_services", agency_client_service_id,
        {"onboarding_status": OnboardingStatus.IMPLEMENTATION_TRIGGERED},
    )
    background_tasks.add_task(run_implementation, agency_client_service_id)
    return {"onboarding_status": "implementation_triggered"}


@app.get("/implementation/reports/{agency_client_service_id}")
async def get_report(agency_client_service_id: str, x_internal_api_key: str | None = Header(default=None)):
    _verify_admin_panel(x_internal_api_key)
    report = await pocketbase.get_record(
        "implementation_reports", f"agency_client_service_id='{agency_client_service_id}'"
    )
    if not report:
        raise HTTPException(status_code=404, detail="no implementation report found for this service")
    return report
