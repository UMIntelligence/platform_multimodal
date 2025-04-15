#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from rest_framework.pagination import PageNumberPagination

from language.language_pack import RET
from utils.cst_class import CstResponse


class CstPageNumberPagination(PageNumberPagination):
    """列表分页自定义分页规则"""
    page_size = 10
    max_page_size = 100
    page_query_param = "page"
    page_size_query_param = "page_size"

    def get_paginated_response(self, data):
        rst = {
            "page_total": self.page.paginator.num_pages,  # [总页数]
            "total": self.page.paginator.count,  # [总条数]
            "page_index": self.page.number,  # [当前页数]
            "data": data
        }

        return CstResponse(RET.OK, data=rst)
