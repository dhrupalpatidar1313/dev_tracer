from rest_framework.views import exception_handler
from rest_framework import status
from rest_framework.exceptions import (
    APIException, ValidationError, ParseError, MethodNotAllowed,
    NotAuthenticated, AuthenticationFailed, PermissionDenied,
    NotFound, UnsupportedMediaType, Throttled
)
from django.http import Http404

class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict"
    default_code = "conflict"

def get_first_error_message(detail, field_name=None, is_brief=True):
    if isinstance(detail, dict):
        for field, errors in detail.items():
            return get_first_error_message(errors, field_name=field, is_brief=is_brief)
    elif isinstance(detail, list) and len(detail) > 0:
        err = detail[0]
        if hasattr(err, 'code') and err.code == 'required' and field_name:
            return f"Missing required field: {field_name}"
        if field_name == 'non_field_errors' or is_brief:
            return str(err)
        return f"{field_name}: {str(err)}"
    return str(detail)

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    view = context.get('view')
    is_brief = getattr(view, 'error_style', None) == 'brief'

    if response is not None:
        if is_brief:
            if isinstance(exc, ValidationError):
                msg = get_first_error_message(exc.detail, is_brief=True)
                response.data = {"error": msg}
            elif isinstance(exc, ParseError):
                response.data = {"error": "Invalid JSON body"}
            elif isinstance(exc, MethodNotAllowed):
                response.data = {"error": "Method not allowed"}
            elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
                response.data = {"error": "Authentication required"}
            elif isinstance(exc, PermissionDenied):
                response.data = {"error": "You do not have permission to perform this action"}
            elif isinstance(exc, (NotFound, Http404)):
                detail = response.data.get('detail', str(exc))
                response.data = {"error": str(detail)}
            elif isinstance(exc, Conflict):
                detail = response.data.get('detail', str(exc))
                response.data = {"error": str(detail)}
            elif isinstance(exc, UnsupportedMediaType):
                response.data = {"error": "Unsupported media type. Use application/json"}
            elif isinstance(exc, Throttled):
                wait = getattr(exc, 'wait', None)
                msg = f"Request was throttled. Try again in {int(wait) if wait else 60} seconds"
                response.data = {"error": msg}
            else:
                detail = response.data.get('detail', str(exc))
                response.data = {"error": str(detail)}
        else:
            # v1 style
            if isinstance(exc, ValidationError):
                msg = get_first_error_message(exc.detail, is_brief=False)
                response.data = {
                    "error": msg,
                    "code": "validation_error",
                    "details": exc.detail
                }
            elif isinstance(exc, ParseError):
                response.data = {"error": "Invalid JSON body", "code": "parse_error"}
            elif isinstance(exc, MethodNotAllowed):
                response.data = {"error": "Method not allowed", "code": "method_not_allowed"}
            elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
                response.data = {"error": "Authentication required", "code": "not_authenticated"}
            elif isinstance(exc, PermissionDenied):
                response.data = {"error": "You do not have permission to perform this action", "code": "permission_denied"}
            elif isinstance(exc, (NotFound, Http404)):
                detail = response.data.get('detail', "Not found")
                response.data = {"error": str(detail), "code": "not_found"}
            elif isinstance(exc, Conflict):
                detail = response.data.get('detail', "Conflict")
                response.data = {"error": str(detail), "code": "conflict"}
            elif isinstance(exc, UnsupportedMediaType):
                response.data = {"error": "Unsupported media type. Use application/json", "code": "unsupported_media_type"}
            elif isinstance(exc, Throttled):
                wait = getattr(exc, 'wait', None)
                msg = f"Request was throttled. Try again in {int(wait) if wait else 60} seconds"
                response.data = {"error": msg, "code": "throttled"}
            else:
                detail = response.data.get('detail', str(exc))
                code = getattr(exc, 'default_code', 'server_error')
                response.data = {"error": str(detail), "code": str(code)}

    return response

