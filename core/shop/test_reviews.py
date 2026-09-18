from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from shop.models import Category, Product, Review

User = get_user_model()


def make_user(username, role=User.Role.CUSTOMER, is_verified=True):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123!",
        role=role,
        is_verified=is_verified,
    )


class ProductReviewAPITests(APITestCase):
    def setUp(self):
        self.author = make_user("reviewer")
        self.other = make_user("otherreviewer")
        self.vendor = make_user("reviewvendor", role=User.Role.VENDOR)
        self.category = Category.objects.create(name="Groceries")
        self.product = Product.objects.create(
            vendor=self.vendor.vendor_profile,
            category=self.category,
            name="Reviewed Honey",
            sku="REV-1",
            price="8.00",
            published=True,
        )
        self.url = reverse(
            "api:api_v1:product-reviews", kwargs={"slug": self.product.slug}
        )

    def test_anonymous_sees_only_approved_reviews(self):
        Review.objects.create(
            user=self.author, product=self.product, score=5, comment="Great", is_approved=True
        )
        Review.objects.create(
            user=self.other,
            product=self.product,
            score=1,
            comment="Pending",
            is_approved=False,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comments = [item["comment"] for item in response.data["results"]]
        self.assertEqual(comments, ["Great"])

    def test_authenticated_user_sees_own_pending_review(self):
        Review.objects.create(
            user=self.author,
            product=self.product,
            score=4,
            comment="Mine pending",
            is_approved=False,
        )
        Review.objects.create(
            user=self.other,
            product=self.product,
            score=1,
            comment="Theirs pending",
            is_approved=False,
        )
        self.client.force_authenticate(user=self.author)

        response = self.client.get(self.url)
        comments = [item["comment"] for item in response.data["results"]]
        self.assertEqual(comments, ["Mine pending"])

    def test_anonymous_cannot_submit_a_review(self):
        response = self.client.post(self.url, {"score": 5, "comment": "Nope"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Review.objects.count(), 0)

    def test_new_review_is_unapproved(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(self.url, {"score": 5, "comment": "Loved it"})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        review = Review.objects.get()
        self.assertEqual(review.user, self.author)
        self.assertFalse(review.is_approved)
        self.assertFalse(response.data["is_approved"])
        self.assertEqual(response.data["score"], 5)

    def test_submitting_again_updates_the_existing_review_and_resets_approval(self):
        Review.objects.create(
            user=self.author,
            product=self.product,
            score=5,
            comment="Old",
            is_approved=True,
        )
        self.client.force_authenticate(user=self.author)
        response = self.client.post(self.url, {"score": 2, "comment": "Changed my mind"})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Review.objects.filter(user=self.author, product=self.product).count(), 1)
        review = Review.objects.get()
        self.assertEqual(review.score, 2)
        self.assertEqual(review.comment, "Changed my mind")
        self.assertFalse(review.is_approved)

    def test_client_cannot_self_approve_a_review(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            self.url, {"score": 5, "comment": "Approve me", "is_approved": True}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(Review.objects.get().is_approved)

    def test_average_rating_ignores_unapproved_reviews(self):
        Review.objects.create(
            user=self.author, product=self.product, score=5, comment="A", is_approved=True
        )
        Review.objects.create(
            user=self.other, product=self.product, score=1, comment="B", is_approved=False
        )

        response = self.client.get(
            reverse("api:api_v1:product-detail", kwargs={"slug": self.product.slug})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["average_rating"], 5)
        self.assertEqual(response.data["review_count"], 1)
