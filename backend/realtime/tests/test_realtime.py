import asyncio
import json

import pytest
from redis import Redis
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.tests.test_authentication import create_account
from organisations.models import Organisation, OrganisationUserRole
from realtime.services import (
    organisation_channel,
    organisation_sequence_key,
    publish_realtime_event,
)
from realtime.streams import organisation_event_stream


def authenticated_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def realtime_accounts(db):
    alpha = Organisation.objects.create(name="Realtime Alpha", slug="realtime-alpha")
    beta = Organisation.objects.create(name="Realtime Beta", slug="realtime-beta")
    alpha_owner, alpha_role = create_account(alpha, "owner-realtime@alpha.test")
    beta_owner, beta_role = create_account(beta, "owner-realtime@beta.test")
    technician, technician_role = create_account(
        alpha,
        "technician-realtime@alpha.test",
        OrganisationUserRole.TECHNICIAN,
    )
    return locals()


@pytest.mark.django_db
def test_realtime_endpoint_requires_authentication():
    response = APIClient().get("/api/v1/realtime/events")

    assert response.status_code == 401
    assert response.data["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
def test_subscription_organisation_is_derived_from_identity(
    realtime_accounts, monkeypatch
):
    subscribed = []

    def fake_stream(organisation_id, **kwargs):
        subscribed.append((organisation_id, kwargs.get("last_event_id")))

        async def content():
            yield "event: connected\ndata: {}\n\n"

        return content()

    monkeypatch.setattr("realtime.views.organisation_event_stream", fake_stream)
    response = authenticated_client(realtime_accounts["alpha_owner"]).get(
        "/api/v1/realtime/events",
        HTTP_LAST_EVENT_ID="42",
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    assert response["Cache-Control"] == "no-cache, no-transform"
    assert subscribed == [(realtime_accounts["alpha"].id, "42")]


@pytest.mark.django_db
def test_invalid_reconnection_cursor_is_rejected(realtime_accounts):
    response = authenticated_client(realtime_accounts["alpha_owner"]).get(
        "/api/v1/realtime/events",
        HTTP_LAST_EVENT_ID="../../other-tenant",
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_redis_fanout_is_strictly_organisation_isolated(realtime_accounts, settings):
    alpha = realtime_accounts["alpha"]
    beta = realtime_accounts["beta"]
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    alpha_subscription = redis.pubsub()
    beta_subscription = redis.pubsub()
    alpha_subscription.subscribe(organisation_channel(alpha.id))
    beta_subscription.subscribe(organisation_channel(beta.id))
    alpha_subscription.get_message(timeout=1)
    beta_subscription.get_message(timeout=1)
    try:
        publish_realtime_event(
            organisation_id=alpha.id,
            event_type="work_order.updated",
            target_id="11111111-1111-1111-1111-111111111111",
            changes={"fields": ["status"]},
        )
        alpha_message = alpha_subscription.get_message(
            ignore_subscribe_messages=True,
            timeout=1,
        )
        beta_message = beta_subscription.get_message(
            ignore_subscribe_messages=True,
            timeout=0.2,
        )
    finally:
        alpha_subscription.close()
        beta_subscription.close()
        redis.delete(organisation_sequence_key(alpha.id))
        redis.delete(organisation_sequence_key(beta.id))
        redis.close()

    event = json.loads(alpha_message["data"])
    assert event["type"] == "work_order.updated"
    assert event["cursor"] == "1"
    assert "organisation" not in event
    assert beta_message is None


@pytest.mark.django_db
def test_work_order_event_is_emitted_only_after_commit(
    realtime_accounts,
    django_capture_on_commit_callbacks,
    monkeypatch,
):
    published = []
    monkeypatch.setattr(
        "realtime.services.publish_realtime_event",
        lambda **event: published.append(event),
    )
    client = authenticated_client(realtime_accounts["alpha_owner"])

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        response = client.post(
            "/api/v1/work-orders",
            {"title": "Realtime pump repair", "siteName": "Plant A"},
            format="json",
        )

    assert response.status_code == 201
    assert published == []
    assert len(callbacks) == 1
    callbacks[0]()
    assert published[0]["event_type"] == "work_order.created"
    assert published[0]["organisation_id"] == realtime_accounts["alpha"].id


@pytest.mark.django_db
def test_publish_failure_never_escapes_or_rolls_back_business_work(
    realtime_accounts, monkeypatch
):
    class UnavailableRedis:
        def eval(self, *args, **kwargs):
            raise ConnectionError("redis unavailable")

    monkeypatch.setattr(
        "realtime.services.Redis.from_url",
        lambda *args, **kwargs: UnavailableRedis(),
    )

    publish_realtime_event(
        organisation_id=realtime_accounts["alpha"].id,
        event_type="work_order.updated",
        target_id="11111111-1111-1111-1111-111111111111",
    )


@pytest.mark.django_db
def test_reconnect_stream_requests_authoritative_refetch(realtime_accounts):
    async def first_event():
        stream = organisation_event_stream(
            realtime_accounts["alpha"].id,
            last_event_id="7",
            heartbeat_seconds=0.05,
            max_connection_seconds=1,
        )
        try:
            return await anext(stream)
        finally:
            await stream.aclose()

    event = asyncio.run(first_event())

    assert "event: sync_required" in event
    assert '"reason":"reconnect"' in event
