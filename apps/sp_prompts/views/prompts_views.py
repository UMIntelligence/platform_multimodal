#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import random

from django.db import connections, transaction
from rest_framework.decorators import action
from rest_framework.viewsets import ViewSet
from rest_framework_extensions.cache.decorators import cache_response

from apps.sp_prompts.sqls import prompts_sqls
from apps.sp_prompts.models.prompts_models import CMModelPromptsType, CMModelPrompts
from language.language_pack import RET
from utils.cst_class import CstResponse
from utils.sql_utils import NewSqlMixin, dict_fetchall

cache_time = 60 * 10


class Prompts(ViewSet, NewSqlMixin):
    """

    """
    query_sql = prompts_sqls.PROMPTS_LIST
    sort_field = ["create_time"]
    main_table = "a"
    where = " and "

    def set_query_sql(self):
        data = self.request.query_params
        is_weight = data.get("is_weight") or ""
        prompts_name = data.get("prompts_name")
        type_name = data.get("type_name")      # type:str
        if is_weight == "1" and not prompts_name:
            self.query_sql += f" and a.is_weight = 1 "
        if prompts_name:
            self.query_sql += f" and b.prompts_name like '%{prompts_name}%' "
        if type_name:
            type_names = type_name.split(",")
            if len(type_names) == 1:
                type_names = "('" + type_names[0] + "')"
            else:
                type_names = tuple(type_names)
            self.query_sql += f" and a.type_name in {type_names} "
        return self.query_sql

    @action(methods=["get"], detail=False)
    # @cache_response(timeout=cache_time, key_func=CstKeyConstructor(), cache='default')
    def type_list(self, request, *args, **kwarg):
        data = CMModelPromptsType.objects.values("type_name", "type_desc")
        return CstResponse(RET.OK, data=data)

    # @cache_response(timeout=cache_time, key_func=CstKeyConstructor(), cache='default')
    def list(self, request, *args, **kwarg):
        """
        会话框列表视图
        :param request:
        :param args:
        :param kwarg:
        :return:
        """
        is_weight = request.query_params.get("is_weight") or ""
        prompts_name = request.query_params.get("prompts_name")
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        if is_weight == "1" and not prompts_name:
            total = -1
            type_list = []
            for i in rows:
                type_name = i["type_name"]
                type_desc = i["type_desc"]
                type_dict = {"type_name": type_name, "type_desc": type_desc}
                if type_dict not in type_list:
                    type_list.append(type_dict)

            for t in type_list:
                t["info"] = []
                type_name = t["type_name"]
                for r in rows:
                    if type_name == r["type_name"]:
                        t["info"].append(r)
            rows = type_list
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    @action(methods=["get"], detail=False)
    def recommend_list(self, request, *args, **kwarg):
        resp = dict()
        with connections["default"].cursor() as cursor:
            cursor.execute(prompts_sqls.RECOMMEND_SQL)
            rows = dict_fetchall(cursor)
        resp["recommend_list"] = random.choices(rows, k=12)
        resp["common"] = rows[:12]
        return CstResponse(RET.OK, data=resp)

    @action(methods=["post"], detail=False)
    def recommend_add(self, request, *args, **kwarg):
        prompts_id = request.data.get("prompts_id")
        if not prompts_id:
            return CstResponse(RET.DATE_ERROR)
        obj = CMModelPrompts.objects.filter(id=prompts_id).first()
        obj.uses_number += 1
        obj.save()
        return CstResponse(RET.OK)

    def create(self, request, *args, **kwarg):
        a = []
        with transaction.atomic():
            for i in a:
                obj = CMModelPromptsType.objects.create(
                    type_name=i["type_name"],
                    type_desc=i["type_desc"],
                )
                for j in i["info"]:
                    CMModelPrompts.objects.create(
                        prompts_type=obj,
                        prompts_name=j["prompts_name"],
                        prompts_desc=j["prompts_desc"],
                        prompts_title=j["prompts_title"],
                    )
        return CstResponse(RET.OK)

