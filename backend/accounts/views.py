from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from accounts.auth import user_from_request
from accounts.models import ApiToken
from accounts.services import (
    AccountError,
    account_payload,
    log_in,
    parse_body,
    provision,
    register,
)


def _json_error(exc):
    return JsonResponse({"error": exc.message}, status=exc.status)


def _authenticated(request):
    user = user_from_request(request)
    if user is None:
        return None, JsonResponse({"error": "Authentication required."}, status=401)
    return user, None


@csrf_exempt
@require_POST
def signup(request):
    try:
        data = parse_body(request)
        user, token = register(
            email=data.get("email", ""),
            password=data.get("password", ""),
            display_name=data.get("display_name", ""),
        )
    except AccountError as exc:
        return _json_error(exc)
    return JsonResponse(account_payload(user, token), status=201)


@csrf_exempt
@require_POST
def login(request):
    try:
        data = parse_body(request)
        user, token = log_in(
            request, email=data.get("email", ""), password=data.get("password", "")
        )
    except AccountError as exc:
        return _json_error(exc)
    return JsonResponse(account_payload(user, token))


@csrf_exempt
@require_POST
def logout(request):
    user, error = _authenticated(request)
    if error is not None:
        return error
    ApiToken.objects.filter(user=user).delete()
    return HttpResponse(status=204)


@csrf_exempt
@require_GET
def me(request):
    user, error = _authenticated(request)
    if error is not None:
        return error
    return JsonResponse(account_payload(user))


@csrf_exempt
@require_POST
def provision_account(request):
    user, error = _authenticated(request)
    if error is not None:
        return error
    provision(user)
    return JsonResponse(account_payload(user))
