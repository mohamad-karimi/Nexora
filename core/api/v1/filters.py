import django_filters

from blog.models import Post as BlogPost
from shop.models import Product


class ProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category__slug")
    vendor = django_filters.CharFilter(field_name="vendor__slug")
    tag = django_filters.CharFilter(field_name="tags__slug")
    min_price = django_filters.NumberFilter(
        field_name="price", lookup_expr="gte"
    )
    max_price = django_filters.NumberFilter(
        field_name="price", lookup_expr="lte"
    )
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")
    color = django_filters.MultipleChoiceFilter(choices=Product.Color.choices)
    condition = django_filters.MultipleChoiceFilter(
        choices=Product.Condition.choices
    )

    class Meta:
        model = Product
        fields = [
            "category",
            "vendor",
            "tag",
            "min_price",
            "max_price",
            "in_stock",
            "color",
            "condition",
        ]

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset.filter(stock=0)


class PostFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category__slug")
    tag = django_filters.CharFilter(field_name="tags__slug")

    class Meta:
        model = BlogPost
        fields = ["category", "tag"]
