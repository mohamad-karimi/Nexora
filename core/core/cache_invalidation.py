"""When public data changes, drop the public cache for its domain.

The single place that says which model changes invalidate which cached
data (see core/public_cache.py for how). Connected once from
shop.apps.ShopConfig.ready().

Domains
-------
catalog  products, product images/specifications/reviews, categories,
         tags, vendors -- everything the product/category/tag/vendor/facet
         endpoints are built from (a category's `product_count`, a vendor's
         `product_count` and the nested category/vendor/tag data on every
         product card all depend on several of these models).
home     home slider slides and banners.
blog     blog posts, categories, tags and likes (`like_count`).

A product's own edits only invalidate when it is or was published: a
vendor working on a draft changes nothing anyone can see, and drafts are
never cached. Stock is covered too -- an order saves the product, so the
storefront's stock/`in_stock` never lags behind a purchase.

Not covered by signals, so left to the TTL: writes that bypass them
(QuerySet.update(), bulk_create(), raw SQL) and blog authors' profile
edits (a profile is re-saved on every login, which would empty the blog
cache constantly).
"""

from django.apps import apps
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_save,
)

from core import public_cache

_TAG_ACTIONS = ("post_add", "post_remove", "post_clear")


def _connect(signal, handler, sender, uid):
    # weak=False: the handlers are closures, which would otherwise be
    # garbage-collected and silently stop invalidating.
    signal.connect(handler, sender=sender, weak=False, dispatch_uid=uid)


def _bump_always(domain):
    def handler(sender, **kwargs):
        public_cache.bump(domain)

    return handler


def _connect_always(label, domain):
    model = apps.get_model(label)
    handler = _bump_always(domain)
    _connect(post_save, handler, model, f"pubcache.{label}.save")
    _connect(post_delete, handler, model, f"pubcache.{label}.delete")


def _connect_public_only(model, domain, field, public_value, uid):
    """Invalidate for a row that is, or just stopped being, public."""

    def remember(sender, instance, **kwargs):
        # pre_save: was the row public before this save?
        instance._was_public = bool(
            instance.pk
            and sender.objects.filter(
                pk=instance.pk, **{field: public_value}
            ).exists()
        )

    def on_save(sender, instance, **kwargs):
        if (
            getattr(instance, "_was_public", False)
            or getattr(instance, field) == public_value
        ):
            public_cache.bump(domain)

    def on_delete(sender, instance, **kwargs):
        if getattr(instance, field) == public_value:
            public_cache.bump(domain)

    _connect(pre_save, remember, model, f"{uid}.pre_save")
    _connect(post_save, on_save, model, f"{uid}.save")
    _connect(post_delete, on_delete, model, f"{uid}.delete")


def connect():
    Product = apps.get_model("shop", "Product")
    Post = apps.get_model("blog", "Post")

    # --- catalog ------------------------------------------------------
    _connect_public_only(
        Product, "catalog", "published", True, "pubcache.shop.Product"
    )

    def related_to_public_product(sender, instance, **kwargs):
        # An image / specification / review only matters once its product
        # is visible in the storefront.
        if Product.objects.filter(
            pk=instance.product_id, published=True
        ).exists():
            public_cache.bump("catalog")

    for label in (
        "shop.ProductImage",
        "shop.ProductSpecification",
        "shop.Review",
    ):
        model = apps.get_model(label)
        _connect(
            post_save,
            related_to_public_product,
            model,
            f"pubcache.{label}.save",
        )
        _connect(
            post_delete,
            related_to_public_product,
            model,
            f"pubcache.{label}.delete",
        )

    def tags_changed(sender, action, **kwargs):
        if action in _TAG_ACTIONS:
            public_cache.bump("catalog")

    _connect(
        m2m_changed,
        tags_changed,
        Product.tags.through,
        "pubcache.shop.Product.tags",
    )

    for label in ("shop.Category", "shop.Tag", "vendors.Vendor"):
        _connect_always(label, "catalog")

    # --- home ---------------------------------------------------------
    for label in ("website.HomeSlide", "website.HomeBanner"):
        _connect_always(label, "home")

    # --- blog ---------------------------------------------------------
    _connect_public_only(
        Post, "blog", "status", Post.Status.PUBLISHED, "pubcache.blog.Post"
    )

    def post_tags_changed(sender, action, **kwargs):
        if action in _TAG_ACTIONS:
            public_cache.bump("blog")

    _connect(
        m2m_changed,
        post_tags_changed,
        Post.tags.through,
        "pubcache.blog.Post.tags",
    )

    for label in ("blog.Category", "blog.Tag", "blog.PostLike"):
        _connect_always(label, "blog")
