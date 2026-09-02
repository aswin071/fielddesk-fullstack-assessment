from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from common.context import get_correlation_id


class FieldDeskPageNumberPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "pageSize"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "data": data,
                "meta": {
                    "page": self.page.number,
                    "pageSize": self.get_page_size(self.request),
                    "total": self.page.paginator.count,
                    "totalPages": self.page.paginator.num_pages,
                    "correlationId": get_correlation_id(),
                },
            }
        )
