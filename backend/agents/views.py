import json

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.auth import user_from_request
from agents.salt.agent import SaltAgent, SaltChatError, prepare_messages
from services.grok import GrokError


def _authenticated(request):
    user = user_from_request(request)
    if user is None:
        return None, JsonResponse({"error": "Authentication required."}, status=401)
    return user, None


def _server_sent_event(name, payload):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {body}\n\n".encode()


@csrf_exempt
@require_POST
def salt_chat(request):
    """Stream Salt's thinking and reply as server-sent events."""
    user, error = _authenticated(request)
    if error is not None:
        return error
    if not request.body:
        return JsonResponse({"error": "Request body must be JSON."}, status=400)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be JSON."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Request body must be a JSON object."}, status=400)
    try:
        messages = prepare_messages(payload.get("messages"))
    except SaltChatError as exc:
        return JsonResponse({"error": exc.message}, status=exc.status)

    agent = SaltAgent()

    def chunks():
        thinking = []
        message = []
        try:
            for event in agent.chat(messages, safety_identifier=str(user.pk)):
                if event.kind == "thinking":
                    thinking.append(event.delta)
                else:
                    message.append(event.delta)
                yield _server_sent_event(event.kind, {"delta": event.delta})
        except GrokError as exc:
            yield _server_sent_event("error", {"error": str(exc)})
            return
        yield _server_sent_event(
            "done",
            {"thinking": "".join(thinking), "message": "".join(message)},
        )

    response = StreamingHttpResponse(chunks(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
