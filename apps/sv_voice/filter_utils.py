#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI


class DigitalHumanCloneFilter(object):
    def filter_queryset(self, request, queryset, obj):
        user_code = request.user.user_code
        queryset = queryset.filter(create_by=user_code)

        return queryset.all()
