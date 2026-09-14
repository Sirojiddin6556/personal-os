"""RFC 9457 Problem Details compliant exception hierarchy and handlers."""

from typing import Any, Dict, List, Optional
from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base domain exception adhering to RFC 9457 Problem Details for HTTP APIs."""

    def __init__(
        self,
        title: str,
        detail: str,
        status: int = 400,
        type_: Optional[str] = None,
        instance: Optional[str] = None,
        invalid_params: Optional[List[Dict[str, Any]]] = None,
        extensions: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(detail)
        self.title = title
        self.detail = detail
        self.status = status
        self.type_ = type_ or f"https://api.personal-os.local/errors/{title.lower().replace(' ', '-')}"
        self.instance = instance
        self.invalid_params = invalid_params or []
        self.extensions = extensions or {}


class NotFoundError(DomainError):
    """Resource was not found in the tenant scope."""

    def __init__(
        self,
        resource: str,
        identifier: Any,
        detail: Optional[str] = None,
        instance: Optional[str] = None,
    ):
        super().__init__(
            title="Resource Not Found",
            detail=detail or f"{resource} with identifier '{identifier}' was not found.",
            status=404,
            type_="https://api.personal-os.local/errors/not-found",
            instance=instance,
            extensions={"resource": resource, "identifier": str(identifier)},
        )


class BadRequestError(DomainError):
    """Bad Request error for malformed headers, wildcards, or invalid syntax (RFC 9110 400)."""

    def __init__(
        self,
        detail: str = "The request was malformed or contains invalid parameters.",
        instance: Optional[str] = None,
        code: str = "BAD_REQUEST",
        extensions: Optional[Dict[str, Any]] = None,
    ):
        ext = {"code": code}
        if extensions:
            ext.update(extensions)
        super().__init__(
            title="Bad Request",
            detail=detail,
            status=400,
            type_="https://api.personal-os.local/errors/bad-request",
            instance=instance,
            extensions=ext,
        )


class ConflictError(DomainError):
    """Conflict occurred, such as invalid state transition or unique constraint violation (RFC 9110 409)."""

    def __init__(
        self,
        title: str = "Resource Conflict",
        detail: str = "A conflict occurred with the current state of the target resource.",
        instance: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            title=title,
            detail=detail,
            status=409,
            type_="https://api.personal-os.local/errors/conflict",
            instance=instance,
            extensions=extensions or {"code": "RESOURCE_CONFLICT"},
        )


class PreconditionRequiredError(DomainError):
    """Precondition header is required (RFC 6585 428)."""

    def __init__(
        self,
        detail: str = "The 'If-Match' precondition header is required to perform this update.",
        instance: Optional[str] = None,
        header: str = "If-Match",
    ):
        super().__init__(
            title="Precondition Required",
            detail=detail,
            status=428,
            type_="https://api.personal-os.local/errors/precondition-required",
            instance=instance,
            extensions={"code": "PRECONDITION_REQUIRED", "required_header": header},
        )


class PreconditionFailedError(DomainError):
    """Precondition header check failed or resource version is stale (RFC 9110 412)."""

    def __init__(
        self,
        detail: str = "The precondition header check failed. The resource version is outdated.",
        resource: Optional[str] = None,
        expected_version: Optional[Any] = None,
        actual_version: Optional[Any] = None,
        instance: Optional[str] = None,
    ):
        ext: Dict[str, Any] = {"code": "STALE_VERSION"}
        if resource:
            ext["resource"] = resource
        if expected_version is not None:
            ext["provided_version"] = expected_version
        if actual_version is not None:
            ext["current_version"] = actual_version
        super().__init__(
            title="Precondition Failed",
            detail=detail,
            status=412,
            type_="https://api.personal-os.local/errors/precondition-failed",
            instance=instance,
            extensions=ext,
        )


class OptimisticLockError(PreconditionFailedError):
    """ETag / version mismatch detected during update (RFC 9110 412)."""

    def __init__(
        self,
        resource: str,
        expected_version: Any,
        actual_version: Any,
        instance: Optional[str] = None,
    ):
        super().__init__(
            detail=(
                f"Resource '{resource}' has been modified by another transaction. "
                f"Provided version {expected_version} does not match current version {actual_version}."
            ),
            resource=resource,
            expected_version=expected_version,
            actual_version=actual_version,
            instance=instance,
        )


class ForbiddenError(DomainError):
    """User lacks sufficient permissions for this workspace or resource."""

    def __init__(
        self,
        detail: str = "You do not have permission to perform this action in this workspace.",
        instance: Optional[str] = None,
    ):
        super().__init__(
            title="Forbidden",
            detail=detail,
            status=403,
            type_="https://api.personal-os.local/errors/forbidden",
            instance=instance,
        )


class UnauthorizedError(DomainError):
    """Authentication required or token expired / invalid."""

    def __init__(
        self,
        detail: str = "Authentication credentials were not provided or are invalid.",
        instance: Optional[str] = None,
    ):
        super().__init__(
            title="Unauthorized",
            detail=detail,
            status=401,
            type_="https://api.personal-os.local/errors/unauthorized",
            instance=instance,
        )


class ValidationDomainError(DomainError):
    """Domain-level semantic validation error."""

    def __init__(
        self,
        detail: str,
        invalid_params: Optional[List[Dict[str, Any]]] = None,
        instance: Optional[str] = None,
    ):
        super().__init__(
            title="Unprocessable Entity",
            detail=detail,
            status=422,
            type_="https://api.personal-os.local/errors/validation-error",
            instance=instance,
            invalid_params=invalid_params,
        )




class RateLimitExceededError(DomainError):
    """Rate limit quota exceeded."""

    def __init__(
        self,
        detail: str = "Too many requests. Please retry later.",
        retry_after_seconds: int = 60,
        instance: Optional[str] = None,
    ):
        super().__init__(
            title="Rate Limit Exceeded",
            detail=detail,
            status=429,
            type_="https://api.personal-os.local/errors/rate-limit-exceeded",
            instance=instance,
            extensions={"retry_after_seconds": retry_after_seconds},
        )


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """FastAPI exception handler converting DomainError to RFC 9457 JSON response."""
    payload: Dict[str, Any] = {
        "type": exc.type_,
        "title": exc.title,
        "status": exc.status,
        "detail": exc.detail,
        "instance": exc.instance or request.url.path,
    }
    if exc.invalid_params:
        payload["invalid-params"] = exc.invalid_params
    if exc.extensions:
        payload.update(exc.extensions)

    return JSONResponse(
        status_code=exc.status,
        content=payload,
        media_type="application/problem+json",
    )
