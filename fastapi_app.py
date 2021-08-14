from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.core.log import logger

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=settings.openapi_url)



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.exception('json validation exception')
    return JSONResponse(content=error_response('validation exception'), status_code=422)

