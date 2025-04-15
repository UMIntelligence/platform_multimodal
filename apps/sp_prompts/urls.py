#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.urls import path

from apps.sp_prompts.views import prompts_views

urlpatterns = [
    path("type_list", prompts_views.Prompts.as_view({"get": "type_list"})),
    path("prompts", prompts_views.Prompts.as_view({"get": "list", "post": "create"})),
    path("recommend", prompts_views.Prompts.as_view({"get": "recommend_list", "post": "recommend_add"})),
]