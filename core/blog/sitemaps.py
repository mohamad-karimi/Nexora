from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Post


class PostSitemap(Sitemap):
    """Mirrors Post.status == PUBLISHED, the same gate the blog
    listing/API already use -- draft/archived posts never appear."""

    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Post.objects.filter(status=Post.Status.PUBLISHED).order_by(
            "-created_date"
        )

    def lastmod(self, post):
        return post.update_date

    def location(self, post):
        return reverse("blog:post_detail", args=[post.slug])
