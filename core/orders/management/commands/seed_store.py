"""
Seed the database with realistic demo data for every model added to the
shop, cart, orders and vendors apps, so each one can be exercised
end-to-end (list views, relations, computed properties, constraints).

Usage:
    python manage.py seed_store            # seed (skips if already seeded)
    python manage.py seed_store --flush     # wipe previously-seeded data, then reseed

Notes:
- Image fields are filled with small generated placeholder PNGs (via
  Pillow, already a project dependency) so gallery/logo/category images
  are non-empty without needing any external assets.
- Everything this command creates is tagged by a fixed set of usernames/
  codes/SKUs, so `--flush` can remove exactly what it added and nothing
  else.
"""

import random
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from cart.models import Cart, CartItem
from orders.models import Address, Coupon, Order, OrderItem, Payment
from shop.models import (
    Category,
    Product,
    ProductImage,
    ProductSpecification,
    Review,
    Tag,
    Wishlist,
)
from vendors.models import Vendor

User = get_user_model()

SEED_PASSWORD = "Passw0rd!123"

VENDOR_USERNAMES = ["green_farm", "daily_bites", "pure_pantry"]
CUSTOMER_USERNAMES = [
    "alice_customer",
    "bob_customer",
    "chloe_customer",
    "daniel_customer",
]

PLACEHOLDER_COLORS = ["4caf50", "ff9800", "2196f3", "e91e63", "795548", "009688"]


def placeholder_image(label, size=(500, 500)):
    """A tiny in-memory PNG so ImageFields have a real file to point to."""
    from PIL import Image, ImageDraw

    color = "#" + random.choice(PLACEHOLDER_COLORS)
    img = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(img)
    draw.text((16, 16), label[:40], fill="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    safe_name = "".join(c if c.isalnum() else "_" for c in label.lower())[:40]
    return ContentFile(buffer.getvalue(), name=f"{safe_name}.png")


VENDOR_DATA = [
    {
        "username": "green_farm",
        "email": "green_farm@nexora.test",
        "store_name": "Green Farm Grocery",
        "phone": "+15550100",
        "description": "Farm-fresh produce and dairy, sourced from local growers.",
    },
    {
        "username": "daily_bites",
        "email": "daily_bites@nexora.test",
        "store_name": "Daily Bites Market",
        "phone": "+15550101",
        "description": "Everyday pantry staples and snacks at fair prices.",
    },
    {
        "username": "pure_pantry",
        "email": "pure_pantry@nexora.test",
        "store_name": "Pure Pantry Co.",
        "phone": "+15550102",
        "description": "Baking essentials and pet care, curated for quality.",
    },
]

CUSTOMER_DATA = [
    {
        "username": "alice_customer",
        "email": "alice@nexora.test",
        "first_name": "Alice",
        "last_name": "Morgan",
    },
    {
        "username": "bob_customer",
        "email": "bob@nexora.test",
        "first_name": "Bob",
        "last_name": "Turner",
    },
    {
        "username": "chloe_customer",
        "email": "chloe@nexora.test",
        "first_name": "Chloe",
        "last_name": "Bennett",
    },
    {
        "username": "daniel_customer",
        "email": "daniel@nexora.test",
        "first_name": "Daniel",
        "last_name": "Reyes",
    },
]

CATEGORY_DATA = [
    {
        "name": "Milk & Dairies",
        "description": "Milk, cheese, yogurt and other dairy products.",
    },
    {"name": "Fresh Fruit", "description": "Seasonal, hand-picked fruit."},
    {"name": "Vegetables", "description": "Fresh vegetables and greens."},
    {"name": "Snacks", "description": "Chips, nuts, bars and other snacks."},
    {
        "name": "Baking Material",
        "description": "Flour, sugar and other baking essentials.",
    },
    {"name": "Pet Foods", "description": "Food and treats for cats and dogs."},
]

TAG_NAMES = [
    "Organic",
    "Gluten-Free",
    "Vegan",
    "Best Seller",
    "New Arrival",
    "Sugar-Free",
]

# Each product: category name, name, sku, price, stock, tags, and optional
# perishable info / discount / specs used to exercise the model's
# computed properties and nullable fields.
PRODUCT_DATA = [
    dict(
        category="Milk & Dairies",
        name="Full Cream Milk 1L",
        sku="DAI-MILK-1L",
        price="3.49",
        stock=120,
        tags=["Best Seller"],
        perishable=(3, 14),
        specs=[("Type of Packing", "Carton"), ("Volume", "1 L")],
    ),
    dict(
        category="Milk & Dairies",
        name="Greek Yogurt 500g",
        sku="DAI-YOG-500",
        price="2.99",
        stock=80,
        tags=["Organic"],
        perishable=(2, 21),
    ),
    dict(
        category="Milk & Dairies",
        name="Cheddar Cheese Block 200g",
        sku="DAI-CHE-200",
        price="4.25",
        stock=45,
        tags=[],
        perishable=(5, 60),
    ),
    dict(
        category="Fresh Fruit",
        name="Red Apple 1kg",
        sku="FRU-APL-1KG",
        price="2.10",
        stock=200,
        tags=["Organic", "Best Seller"],
        perishable=(2, 30),
        product_type="Organic",
        discount_percent=15,
        discount_days=7,
    ),
    dict(
        category="Fresh Fruit",
        name="Organic Kiwi 500g",
        sku="FRU-KIW-500",
        price="3.60",
        stock=90,
        tags=["Organic"],
        perishable=(3, 21),
    ),
    dict(
        category="Fresh Fruit",
        name="Black Plum 1kg",
        sku="FRU-PLM-1KG",
        price="2.80",
        stock=70,
        tags=[],
        perishable=(2, 14),
    ),
    dict(
        category="Vegetables",
        name="Fresh Carrot 1kg",
        sku="VEG-CAR-1KG",
        price="1.45",
        stock=150,
        tags=["Organic"],
        perishable=(2, 21),
    ),
    dict(
        category="Vegetables",
        name="Organic Spinach 250g",
        sku="VEG-SPN-250",
        price="1.99",
        stock=60,
        tags=["Organic", "Vegan"],
        perishable=(1, 7),
    ),
    dict(
        category="Vegetables",
        name="Broccoli Head",
        sku="VEG-BRO-1EA",
        price="1.75",
        stock=55,
        tags=["Vegan"],
        perishable=(1, 10),
    ),
    dict(
        category="Snacks",
        name="Roasted Almonds 200g",
        sku="SNK-ALM-200",
        price="5.50",
        stock=100,
        tags=["Vegan", "Best Seller"],
        product_type="Organic",
        specs=[
            ("Type of Packing", "Bag"),
            ("Quantity per Case", "12"),
            ("Weight", "200 g"),
        ],
    ),
    dict(
        category="Snacks",
        name="Potato Chips Classic 150g",
        sku="SNK-CHP-150",
        price="1.80",
        stock=300,
        tags=[],
    ),
    dict(
        category="Snacks",
        name="Granola Bar Box (6 pcs)",
        sku="SNK-GRN-6PK",
        price="4.00",
        stock=40,
        tags=["New Arrival"],
        discount_percent=10,
        discount_days=-1,
    ),  # expired discount, on purpose
    dict(
        category="Baking Material",
        name="All-Purpose Flour 1kg",
        sku="BAK-FLR-1KG",
        price="1.60",
        stock=130,
        tags=[],
    ),
    dict(
        category="Baking Material",
        name="Brown Sugar 900g",
        sku="BAK-SUG-900",
        price="2.20",
        stock=95,
        tags=[],
    ),
    dict(
        category="Baking Material",
        name="Baking Powder 100g",
        sku="BAK-PDR-100",
        price="1.10",
        stock=200,
        tags=[],
    ),
    dict(
        category="Pet Foods",
        name="Dry Dog Food 3kg",
        sku="PET-DOG-3KG",
        price="12.99",
        stock=35,
        tags=["Best Seller"],
        specs=[
            ("Type of Packing", "Bag"),
            ("Suitable for", "Adult dogs"),
            ("Weight", "3 kg"),
        ],
    ),
    dict(
        category="Pet Foods",
        name="Cat Treats Salmon 100g",
        sku="PET-CAT-100",
        price="3.30",
        stock=60,
        tags=["New Arrival"],
    ),
    dict(
        category="Pet Foods",
        name="Bird Seed Mix 1kg",
        sku="PET-BRD-1KG",
        price="2.50",
        stock=40,
        tags=[],
        stock_zero_demo=True,
    ),
]

REVIEW_DATA = [
    (
        "DAI-MILK-1L",
        "alice_customer",
        5,
        "Tastes fresh, delivered cold. Will buy again.",
        True,
    ),
    ("DAI-MILK-1L", "bob_customer", 4, "Good quality but a bit pricey.", True),
    ("FRU-APL-1KG", "chloe_customer", 5, "Crisp and sweet, kids love them.", True),
    ("FRU-APL-1KG", "daniel_customer", 3, "Half the batch was bruised.", False),
    ("SNK-ALM-200", "alice_customer", 5, "Great snack, nicely roasted.", True),
    ("SNK-CHP-150", "bob_customer", 4, "Classic taste, good portion size.", True),
    (
        "PET-DOG-3KG",
        "chloe_customer",
        5,
        "My dog loves it, coat looks healthier already.",
        True,
    ),
    ("VEG-SPN-250", "daniel_customer", 2, "Arrived wilted, not very fresh.", False),
]

WISHLIST_DATA = [
    ("alice_customer", "FRU-KIW-500"),
    ("alice_customer", "PET-CAT-100"),
    ("bob_customer", "DAI-CHE-200"),
    ("chloe_customer", "SNK-GRN-6PK"),
    ("daniel_customer", "BAK-SUG-900"),
]

COUPON_DATA = [
    dict(
        code="WELCOME10",
        discount_percent=10,
        from_days=-30,
        to_days=60,
        usage_limit=None,
        used_count=12,
    ),
    dict(
        code="SUMMER20",
        discount_percent=20,
        from_days=-5,
        to_days=25,
        usage_limit=100,
        used_count=8,
    ),
    dict(
        code="EXPIRED5",
        discount_percent=5,
        from_days=-60,
        to_days=-10,
        usage_limit=50,
        used_count=50,
    ),
]


class Command(BaseCommand):
    help = "Seed demo data for the shop, cart, orders and vendors models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete previously-seeded store data before reseeding.",
        )

    def handle(self, *args, **options):
        random.seed(42)

        if options["flush"]:
            self._flush()

        if (
            not options["flush"]
            and Vendor.objects.filter(user__username=VENDOR_USERNAMES[0]).exists()
        ):
            self.stdout.write(
                self.style.WARNING(
                    "Seed data already present - skipping. Re-run with --flush to reseed."
                )
            )
            return

        with transaction.atomic():
            vendors = self._seed_vendors()
            customers = self._seed_customers()
            categories = self._seed_categories()
            tags = self._seed_tags()
            products = self._seed_products(vendors, categories, tags)
            self._seed_reviews(customers, products)
            self._seed_wishlist(customers, products)
            addresses = self._seed_addresses(customers)
            coupons = self._seed_coupons()
            self._seed_carts(customers, products)
            self._seed_orders(customers, addresses, coupons, products)

        self.stdout.write(self.style.SUCCESS("Store data seeded successfully."))

    # -- teardown -----------------------------------------------------
    def _flush(self):
        Payment.objects.filter(order__user__username__in=CUSTOMER_USERNAMES).delete()
        OrderItem.objects.filter(order__user__username__in=CUSTOMER_USERNAMES).delete()
        Order.objects.filter(user__username__in=CUSTOMER_USERNAMES).delete()
        CartItem.objects.filter(cart__user__username__in=CUSTOMER_USERNAMES).delete()
        Cart.objects.filter(user__username__in=CUSTOMER_USERNAMES).delete()
        Wishlist.objects.filter(user__username__in=CUSTOMER_USERNAMES).delete()
        Review.objects.filter(user__username__in=CUSTOMER_USERNAMES).delete()
        ProductSpecification.objects.filter(
            product__sku__in=[p["sku"] for p in PRODUCT_DATA]
        ).delete()
        ProductImage.objects.filter(
            product__sku__in=[p["sku"] for p in PRODUCT_DATA]
        ).delete()
        Product.objects.filter(sku__in=[p["sku"] for p in PRODUCT_DATA]).delete()
        Tag.objects.filter(name__in=TAG_NAMES).delete()
        Category.objects.filter(name__in=[c["name"] for c in CATEGORY_DATA]).delete()
        Address.objects.filter(user__username__in=CUSTOMER_USERNAMES).delete()
        Coupon.objects.filter(code__in=[c["code"] for c in COUPON_DATA]).delete()
        Vendor.objects.filter(user__username__in=VENDOR_USERNAMES).delete()
        User.objects.filter(username__in=VENDOR_USERNAMES + CUSTOMER_USERNAMES).delete()
        self.stdout.write(self.style.WARNING("Previously-seeded store data removed."))

    # -- seeders --------------------------------------------------------
    def _seed_vendors(self):
        vendors = []
        for data in VENDOR_DATA:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={
                    "email": data["email"],
                    "role": User.Role.VENDOR,
                    "is_verified": True,
                },
            )
            if created:
                user.set_password(SEED_PASSWORD)
                user.save()
                profile = user.profile
                profile.first_name = data["store_name"].split()[0]
                profile.last_name = "Vendor"
                profile.display_name = data["store_name"]
                profile.phone = data["phone"]
                profile.address = "123 Market Street"
                profile.description = data["description"]
                profile.save()

            # vendors.signals already creates a bare Vendor row as soon
            # as `user` is saved with role=Vendor above (get_or_create's
            # own initial save included), so get_or_create here would
            # find that bare row and skip `defaults` entirely. Fetch
            # (or create, for safety) then always apply the seed data.
            vendor, _ = Vendor.objects.get_or_create(user=user)
            vendor.store_name = data["store_name"]
            vendor.phone = data["phone"]
            vendor.email = data["email"]
            vendor.address = "123 Market Street"
            vendor.description = data["description"]
            vendor.is_approved = True
            vendor.save()
            if not vendor.logo:
                vendor.logo.save(
                    f"{vendor.slug}.png",
                    placeholder_image(vendor.store_name),
                    save=True,
                )
            vendors.append(vendor)
        return vendors

    def _seed_customers(self):
        customers = []
        for data in CUSTOMER_DATA:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={
                    "email": data["email"],
                    "role": User.Role.CUSTOMER,
                    "is_verified": True,
                },
            )
            if created:
                user.set_password(SEED_PASSWORD)
                user.save()
                profile = user.profile
                profile.first_name = data["first_name"]
                profile.last_name = data["last_name"]
                profile.display_name = f"{data['first_name']} {data['last_name']}"
                profile.phone = "+1555020" + str(len(customers))
                profile.address = "45 Residential Ave"
                profile.description = "Regular customer."
                profile.save()
            customers.append(user)
        return customers

    def _seed_categories(self):
        categories = {}
        for data in CATEGORY_DATA:
            category, _ = Category.objects.get_or_create(
                name=data["name"], defaults={"description": data["description"]}
            )
            if not category.image:
                category.image.save(
                    f"{category.slug}.png", placeholder_image(category.name), save=True
                )
            categories[data["name"]] = category
        return categories

    def _seed_tags(self):
        tags = {}
        for name in TAG_NAMES:
            tag, _ = Tag.objects.get_or_create(name=name)
            tags[name] = tag
        return tags

    def _seed_products(self, vendors, categories, tags):
        products = {}
        today = timezone.now().date()
        for i, data in enumerate(PRODUCT_DATA):
            vendor = vendors[i % len(vendors)]
            category = categories[data["category"]]

            manufacture_date = None
            shelf_life_days = None
            if "perishable" in data:
                days_ago, shelf_life_days = data["perishable"]
                manufacture_date = today - timedelta(days=days_ago)

            discount_percent = data.get("discount_percent", 0)
            discount_end = None
            if "discount_days" in data:
                discount_end = timezone.now() + timedelta(days=data["discount_days"])

            stock = 0 if data.get("stock_zero_demo") else data["stock"]

            product, created = Product.objects.get_or_create(
                sku=data["sku"],
                defaults={
                    "vendor": vendor,
                    "category": category,
                    "name": data["name"],
                    "short_description": f"{data['name']} - sourced by {vendor.store_name}.",
                    "description": f"{data['name']} available at {vendor.store_name}. "
                    "Quality checked before dispatch.",
                    "price": Decimal(data["price"]),
                    "discount_percent": discount_percent,
                    "discount_end": discount_end,
                    "stock": stock,
                    "product_type": data.get("product_type", ""),
                    "manufacture_date": manufacture_date,
                    "shelf_life_days": shelf_life_days,
                    "status": Product.Status.PUBLISHED,
                    "published": True,
                },
            )
            if created:
                if data["tags"]:
                    product.tags.set([tags[name] for name in data["tags"]])

                product.image.save(
                    f"{product.slug}.png", placeholder_image(product.name), save=True
                )
                for n in range(2):
                    ProductImage.objects.create(
                        product=product,
                        image=placeholder_image(f"{product.name} {n + 1}"),
                        is_primary=(n == 0),
                        ordering=n,
                    )

                for spec_name, spec_value in data.get("specs", []):
                    ProductSpecification.objects.create(
                        product=product, name=spec_name, value=spec_value
                    )

            products[data["sku"]] = product
        return products

    def _seed_reviews(self, customers, products):
        customers_by_username = {u.username: u for u in customers}
        for sku, username, score, comment, approved in REVIEW_DATA:
            Review.objects.get_or_create(
                user=customers_by_username[username],
                product=products[sku],
                defaults={"score": score, "comment": comment, "is_approved": approved},
            )

    def _seed_wishlist(self, customers, products):
        customers_by_username = {u.username: u for u in customers}
        for username, sku in WISHLIST_DATA:
            Wishlist.objects.get_or_create(
                user=customers_by_username[username], product=products[sku]
            )

    def _seed_addresses(self, customers):
        addresses = {}
        cities = ["Baku", "Berlin", "Toronto", "Austin"]
        for i, user in enumerate(customers):
            addr, _ = Address.objects.get_or_create(
                user=user,
                address_type=Address.AddressType.BOTH,
                defaults={
                    "full_name": user.profile.display_name or user.username,
                    "phone": user.profile.phone or "+15550000",
                    "country": "Neverland",
                    "city": cities[i % len(cities)],
                    "postal_code": f"{10000 + i}",
                    "address_line1": f"{100 + i} Residential Ave",
                    "address_line2": "Apt " + str(i + 1),
                    "is_default": True,
                },
            )
            addresses[user.username] = addr
        return addresses

    def _seed_coupons(self):
        coupons = {}
        now = timezone.now()
        for data in COUPON_DATA:
            coupon, _ = Coupon.objects.get_or_create(
                code=data["code"],
                defaults={
                    "discount_percent": data["discount_percent"],
                    "valid_from": now + timedelta(days=data["from_days"]),
                    "valid_to": now + timedelta(days=data["to_days"]),
                    "usage_limit": data["usage_limit"],
                    "used_count": data["used_count"],
                    "is_active": True,
                },
            )
            coupons[data["code"]] = coupon
        return coupons

    def _seed_carts(self, customers, products):
        # Alice: a logged-in cart with a couple of items still shopping.
        alice = customers[0]
        cart, _ = Cart.objects.get_or_create(user=alice)
        for sku, qty in [("VEG-CAR-1KG", 2), ("SNK-CHP-150", 3)]:
            CartItem.objects.get_or_create(
                cart=cart, product=products[sku], defaults={"quantity": qty}
            )

        # A guest cart (no user yet) to exercise the session-based path.
        guest_cart, _ = Cart.objects.get_or_create(
            session_key="demo-guest-session-key-0001"
        )
        CartItem.objects.get_or_create(
            cart=guest_cart, product=products["FRU-KIW-500"], defaults={"quantity": 1}
        )

    def _seed_orders(self, customers, addresses, coupons, products):
        bob, chloe, daniel = customers[1], customers[2], customers[3]

        # Order 1: Bob, delivered, paid, with a coupon applied.
        self._create_order(
            user=bob,
            address=addresses["bob_customer"],
            coupon=coupons["WELCOME10"],
            items=[("DAI-MILK-1L", 2), ("SNK-ALM-200", 1)],
            products=products,
            status=Order.Status.DELIVERED,
            shipping_cost=Decimal("4.00"),
            payment_status=Payment.Status.SUCCESS,
            tracking_code="TRK-BOB-0001",
        )

        # Order 2: Chloe, shipped, paid, no coupon.
        self._create_order(
            user=chloe,
            address=addresses["chloe_customer"],
            coupon=None,
            items=[("PET-DOG-3KG", 1), ("PET-CAT-100", 2)],
            products=products,
            status=Order.Status.SHIPPED,
            shipping_cost=Decimal("6.50"),
            payment_status=Payment.Status.SUCCESS,
            tracking_code="TRK-CHLOE-0001",
        )

        # Order 3: Daniel, still pending payment (tests the non-success path).
        self._create_order(
            user=daniel,
            address=addresses["daniel_customer"],
            coupon=coupons["SUMMER20"],
            items=[("BAK-FLR-1KG", 3), ("BAK-SUG-900", 2), ("BAK-PDR-100", 1)],
            products=products,
            status=Order.Status.PENDING,
            shipping_cost=Decimal("3.00"),
            payment_status=Payment.Status.PENDING,
            tracking_code="",
        )

    def _create_order(
        self,
        user,
        address,
        coupon,
        items,
        products,
        status,
        shipping_cost,
        payment_status,
        tracking_code,
    ):
        if Order.objects.filter(
            user=user, tracking_code=tracking_code, tracking_code__gt=""
        ).exists():
            return

        order = Order.objects.create(
            user=user,
            shipping_address=address,
            billing_address=address,
            coupon=coupon,
            shipping_cost=shipping_cost,
            discount_amount=Decimal("0"),
            total_amount=Decimal("0"),
            status=status,
            tracking_code=tracking_code,
        )

        for sku, qty in items:
            product = products[sku]
            OrderItem.objects.create(
                order=order, product=product, quantity=qty, unit_price=product.price
            )

        discount_amount = Decimal("0")
        if coupon:
            discount_amount = (order.subtotal * coupon.discount_percent / 100).quantize(
                Decimal("0.01")
            )

        order.discount_amount = discount_amount
        order.total_amount = order.subtotal + shipping_cost - discount_amount
        order.save(update_fields=["discount_amount", "total_amount"])

        Payment.objects.create(
            order=order,
            amount=order.total_amount,
            transaction_id=f"TXN-{order.order_number}",
            payment_method=Payment.Method.CARD,
            status=payment_status,
            paid_at=(
                timezone.now() if payment_status == Payment.Status.SUCCESS else None
            ),
        )
