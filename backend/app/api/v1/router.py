from fastapi import APIRouter

from app.api.v1 import (
    admin,
    analytics,
    auth,
    clinical,
    consent_docs,
    datasets,
    prescriptions,
    rbac_check,
    registration,
    research_eval,
    therapeutic_alternatives,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(registration.router)
api_router.include_router(consent_docs.router)
api_router.include_router(admin.router)
api_router.include_router(rbac_check.router)
api_router.include_router(prescriptions.router)
api_router.include_router(clinical.router)
api_router.include_router(therapeutic_alternatives.router)
api_router.include_router(analytics.router)
api_router.include_router(datasets.router)
api_router.include_router(research_eval.router)
