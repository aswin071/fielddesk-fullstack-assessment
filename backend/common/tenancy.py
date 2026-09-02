from django.shortcuts import get_object_or_404


def organisation_object_or_404(queryset, actor, **lookup):
    """Fetch only inside the actor's organisation to avoid cross-tenant ID probing."""

    return get_object_or_404(queryset.for_organisation(actor.organisation), **lookup)

