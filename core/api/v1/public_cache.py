"""DRF mixins that serve PUBLIC list/detail queries from core.public_cache.

They cache the query result (model instances plus the total count), never
the HTTP response: the serializer, the pagination links and every
per-user field (`is_wishlisted`, `is_liked`, ...) still run on each
request. See core/public_cache.py for the rules and the invalidation.

A request is only cached when it is a plain public read: every query
parameter must be one the viewset declares cacheable and carry a
well-formed value (so arbitrary `?search=`/`?min_price=`/junk parameters
cannot fill Redis with one-off entries), and an empty result is never
stored (an unknown slug would otherwise create a key per typo).
Everything else goes straight to the database exactly as before.
"""

import re

from rest_framework.response import Response

from core import public_cache

_SLUG = re.compile(r"^[-\w]{1,200}$")
_TOKEN = re.compile(r"^[\w.-]{1,50}$")
_MAX_VALUES_PER_PARAM = 5
_MAX_PAGE = 1000


class _PrecomputedResults:
    """Stands in for a queryset when the page was served from the cache.

    Just enough for DRF's PageNumberPagination / Django's Paginator: the
    total count, and slicing that hands back the cached page's objects.
    """

    def __init__(self, count, objects):
        self._count = count
        self._objects = objects

    def count(self):
        return self._count

    def __len__(self):
        return self._count

    def __getitem__(self, key):
        return self._objects


class PublicListCacheMixin:
    """Cache `list()` for a public, user-independent queryset."""

    public_cache_domain = None
    public_cache_ttl = None  # key of settings.PUBLIC_CACHE_TTL
    public_cache_name = None  # which endpoint (part of every key)
    # Query parameters a cacheable request may carry, and the allowed
    # values of `ordering`. Anything else is served uncached.
    public_cache_params = frozenset()
    public_cache_slug_params = frozenset()
    public_cache_orderings = frozenset()

    def _public_cache_parts(self, request):
        """Key parts for this request, or None if it must not be cached."""
        normalized = {}
        for name, values in request.query_params.lists():
            if name not in self.public_cache_params:
                return None
            if len(values) > _MAX_VALUES_PER_PARAM:
                return None
            for value in values:
                if name == "ordering":
                    ok = value in self.public_cache_orderings
                elif name == "page":
                    ok = value.isdigit() and 0 < int(value) <= _MAX_PAGE
                elif name == "page_size":
                    max_size = getattr(self.paginator, "max_page_size", 0)
                    ok = value.isdigit() and 0 < int(value) <= max_size
                elif name in self.public_cache_slug_params:
                    ok = bool(_SLUG.match(value))
                else:
                    ok = bool(_TOKEN.match(value))
                if not ok:
                    return None
            normalized[name] = sorted(values)
        return [self.public_cache_name, sorted(normalized.items())]

    def list(self, request, *args, **kwargs):
        parts = (
            self._public_cache_parts(request)
            if public_cache.available()
            else None
        )
        if parts is None:
            return super().list(request, *args, **kwargs)

        slot = public_cache.lookup(self.public_cache_domain, *parts)
        if slot.hit:
            paged, count, objects = slot.value
            if paged:
                # Rebuilds the paginator state (links, count) from the
                # cached page; raises the same NotFound for a bad page.
                objects = self.paginate_queryset(
                    _PrecomputedResults(count, objects)
                )
        else:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            paged = page is not None
            if paged:
                objects = list(page)
                count = self.paginator.page.paginator.count
            else:
                objects = list(queryset)
                count = len(objects)
            if count:
                public_cache.store(
                    slot, (paged, count, objects), self.public_cache_ttl
                )

        serializer = self.get_serializer(objects, many=True)
        if paged:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class PublicDetailCacheMixin:
    """Cache `retrieve()`'s object -- only when it is public.

    `is_public(obj)` decides. An object the viewset lets only its owner or
    staff see (e.g. an unpublished product) is never stored, so it can
    never be handed to anyone else from the cache; and it is only ever
    looked up for a request with no query parameters (the filter backends
    could otherwise change what the URL resolves to).
    """

    public_cache_domain = None
    public_cache_ttl = None
    public_cache_name = None

    def public_cache_is_public(self, obj):
        raise NotImplementedError

    def get_object_uncached(self):
        """The viewset's normal lookup, with all its visibility rules.

        A viewset that customizes get_object() (e.g. to let an owner see
        their unpublished item) defines that logic under this name
        instead.
        """
        return super().get_object()

    def get_object(self):
        if (
            self.action != "retrieve"
            or self.request.query_params
            or not public_cache.available()
        ):
            return self.get_object_uncached()
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        slug = self.kwargs.get(lookup_url_kwarg, "")
        if not _SLUG.match(slug):
            return self.get_object_uncached()

        slot = public_cache.lookup(
            self.public_cache_domain, self.public_cache_name, "detail", slug
        )
        if slot.hit:
            obj = slot.value
            self.check_object_permissions(self.request, obj)
            return obj
        obj = self.get_object_uncached()
        if self.public_cache_is_public(obj):
            public_cache.store(slot, obj, self.public_cache_ttl)
        return obj
