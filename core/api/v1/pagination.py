from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Default pagination for the whole API. `page_size` is client-settable
    (the theme's "Show: 50/100/150/200/All" dropdowns map straight onto
    it) but capped so a client can't force an unbounded query.
    """

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 200
