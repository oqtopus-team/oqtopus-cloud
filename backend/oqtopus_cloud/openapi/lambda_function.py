import pathlib

from fastapi import APIRouter, FastAPI
from fastapi.responses import Response

router = APIRouter()
app: FastAPI = FastAPI()


@router.get("/openapi.yaml")
async def get_openapi_yaml():
    filepath = pathlib.Path(__file__).parent / "openapi.yaml"
    content = filepath.read_text()
    return Response(content, media_type="application/yaml")


app.include_router(router)
