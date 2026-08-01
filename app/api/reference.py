from fastapi import APIRouter

from app.core.reference_data import config_reference, houses_meanings, lots_library, rulerships

router = APIRouter(prefix="/api/reference", tags=["reference"])


@router.get("/config")
def get_config():
    return config_reference()


@router.get("/houses")
def get_houses_meanings():
    return houses_meanings()


@router.get("/rulerships")
def get_rulerships():
    return rulerships()


@router.get("/lots")
def get_lots():
    return lots_library()
