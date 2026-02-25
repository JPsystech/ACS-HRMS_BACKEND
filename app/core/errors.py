"""
Central error handling for ACS HRMS Backend
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from typing import Union


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTPException with consistent JSON response format
    
    Args:
        request: FastAPI request object
        exc: HTTPException instance
    
    Returns:
        JSONResponse with error details
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": str(request.url.path)
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle RequestValidationError with consistent JSON response format
    
    Does not leak internal validation details in production.
    
    Args:
        request: FastAPI request object
        exc: RequestValidationError instance
    
    Returns:
        JSONResponse with error details
    """
    from app.core.config import settings
    
    # In production, return generic error message
    if settings.APP_ENV == "prod":
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": True,
                "status_code": 422,
                "detail": "Validation error: Invalid request data",
                "path": str(request.url.path)
            }
        )
    
    # In development/staging, return detailed errors (sanitize for JSON: e.g. ctx.error ValueError -> str)
    raw_errors = exc.errors()
    errors = []
    for e in raw_errors:
        err = dict(e)
        if "ctx" in err and isinstance(err["ctx"], dict):
            ctx = {k: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v) for k, v in err["ctx"].items()}
            err["ctx"] = ctx
        errors.append(err)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "status_code": 422,
            "detail": "Validation error",
            "errors": errors,
            "path": str(request.url.path)
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions with consistent JSON response format
    
    Does not leak internal error details in production.
    
    Args:
        request: FastAPI request object
        exc: Exception instance
    
    Returns:
        JSONResponse with error details
    """
    from app.core.config import settings
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Log full traceback for debugging
    if settings.APP_ENV != "prod":
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    # In production, return generic error message
    if settings.APP_ENV == "prod":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "status_code": 500,
                "detail": "Internal server error",
                "path": str(request.url.path)
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )
    
    # In development/staging, return error details
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "status_code": 500,
            "detail": str(exc),
            "path": str(request.url.path),
            "traceback": traceback.format_exc() if settings.APP_ENV == "local" else None
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )
