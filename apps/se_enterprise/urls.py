#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.urls import path

from apps.se_enterprise.views import enterprise_collect

urlpatterns = [
    path("list", enterprise_collect.EnterpriseInfo.as_view({"get": "list"})),
    path("retrieve", enterprise_collect.EnterpriseInfo.as_view({"get": "retrieve"})),
    path("company_update", enterprise_collect.EnterpriseInfo.as_view({"post": "company_update"})),
    path("company_create_or_update", enterprise_collect.EnterpriseInfo.as_view({"post": "company_create_or_update"})),
    path("project_create_or_update", enterprise_collect.EnterpriseInfo.as_view({"post": "project_create_or_update"})),
    path("information_create_or_update", enterprise_collect.EnterpriseInfo.as_view({"post": "information_create_or_update"})),
    path("knowledge_create_or_update", enterprise_collect.EnterpriseInfo.as_view({"post": "knowledge_create_or_update"})),

    path("knowledge_list", enterprise_collect.KnowledgeView.as_view({"get": "list"})),
    path("knowledge_view/<str:knowledge_code>", enterprise_collect.KnowledgeView.as_view({"delete": "destroy"})),

    # 企业成员
    path("enterprise_member", enterprise_collect.EnterpriseMemberView.as_view({"get": "list", "post": "create"})),
    path("enterprise_member/<str:member_code>", enterprise_collect.EnterpriseMemberView.as_view({"put": "examine",
                                                                                                 "delete": "destroy"})),

    # 数字员工
    path("digital_clerk", enterprise_collect.EnterpriseDigitalClerkView.as_view({"get": "list", "post": "create"})),

    path("digital_clerk/<str:clerk_code>", enterprise_collect.EnterpriseDigitalClerkView.as_view({"put": "update",
                                                                                                  "delete": "destroy",
                                                                                                  "get": "retrieve"})),

    # 标签
    path("enterprise_label", enterprise_collect.EnterpriseLabel.as_view({"get": "list"})),
]
