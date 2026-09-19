from django.contrib.syndication.views import Feed
from django.urls import reverse

from .models import Post


class BlogFeed(Feed):
    """
    /blog/feed/ -- published posts only (mirrors the same
    Post.status == PUBLISHED gate the blog listing/API use). Item
    links/the feed's own <link> are resolved to absolute URLs by
    Django's syndication framework via the current Site's domain
    (django.contrib.sites), so nothing here hardcodes a host.
    """

    title = "Nexora Blog"
    description = "Latest published posts from the Nexora blog."

    def link(self):
        return reverse("blog:category_list")

    def items(self):
        return Post.objects.filter(status=Post.Status.PUBLISHED).order_by(
            "-created_date"
        )[:50]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.excerpt or item.content[:300]

    def item_link(self, item):
        return reverse("blog:post_detail", args=[item.slug])

    def item_pubdate(self, item):
        return item.created_date

    def item_updateddate(self, item):
        return item.update_date

    def item_author_name(self, item):
        # CustomUser is AbstractBaseUser-based (no first/last name, no
        # get_full_name()) -- username is the only display name it has.
        if item.author_id:
            return item.author.get_username()
        return None
