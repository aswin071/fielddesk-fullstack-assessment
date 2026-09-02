from rest_framework.response import Response

from common.context import get_correlation_id


def success_response(data=None, *, status_code=200, meta=None, headers=None):
    response_meta = dict(meta or {})
    correlation_id = get_correlation_id()
    if correlation_id:
        response_meta["correlationId"] = correlation_id
    return Response(
        {"data": data, "meta": response_meta},
        status=status_code,
        headers=headers,
    )

