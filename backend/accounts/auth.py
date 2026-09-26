from accounts.models import ApiToken


def user_from_request(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    key = header.removeprefix("Bearer ").strip()
    if not key:
        return None
    token = ApiToken.objects.select_related("user").filter(key=key).first()
    if token is None:
        return None
    return token.user
