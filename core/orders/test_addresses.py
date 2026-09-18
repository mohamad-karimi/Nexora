from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from orders.models import Address

User = get_user_model()


def make_user(username, is_verified=True):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123!",
        is_verified=is_verified,
    )


def address_payload(**overrides):
    payload = {
        "full_name": "Ada Lovelace",
        "phone": "09120000000",
        "country": "Iran",
        "city": "Tehran",
        "postal_code": "12345",
        "address_line1": "1 Example St",
        "address_type": Address.AddressType.BOTH,
    }
    payload.update(overrides)
    return payload


class AddressAPITests(APITestCase):
    def setUp(self):
        self.user = make_user("addruser")
        self.other = make_user("addrother")
        self.list_url = reverse("api:api_v1:address-list")
        self.client.force_authenticate(user=self.user)

    def test_anonymous_cannot_list_addresses(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.list_url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_create_and_list_own_addresses(self):
        response = self.client.post(self.list_url, address_payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Address.objects.get().user, self.user)

        listed = self.client.get(self.list_url)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data["results"]), 1)

    def test_user_cannot_read_update_or_delete_another_users_address(self):
        foreign = Address.objects.create(
            user=self.other,
            full_name="Other Person",
            phone="000",
            country="Iran",
            city="Shiraz",
            postal_code="00000",
            address_line1="Hidden",
        )
        url = reverse("api:api_v1:address-detail", kwargs={"pk": foreign.pk})

        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.patch(url, {"city": "Hacked"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND)
        foreign.refresh_from_db()
        self.assertEqual(foreign.city, "Shiraz")

    def test_cannot_delete_the_only_remaining_address(self):
        created = self.client.post(self.list_url, address_payload())
        url = reverse("api:api_v1:address-detail", kwargs={"pk": created.data["id"]})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Address.objects.filter(user=self.user).exists())

    def test_can_delete_an_address_when_another_remains(self):
        first = self.client.post(self.list_url, address_payload(city="Tehran"))
        self.client.post(
            self.list_url, address_payload(city="Isfahan", postal_code="2")
        )
        url = reverse("api:api_v1:address-detail", kwargs={"pk": first.data["id"]})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Address.objects.filter(user=self.user).count(), 1)

    def test_list_does_not_include_another_users_addresses(self):
        Address.objects.create(
            user=self.other,
            full_name="Other Person",
            phone="000",
            country="Iran",
            city="Shiraz",
            postal_code="00000",
            address_line1="Hidden",
        )
        self.client.post(self.list_url, address_payload())

        response = self.client.get(self.list_url)
        cities = [item["city"] for item in response.data["results"]]
        self.assertEqual(cities, ["Tehran"])
