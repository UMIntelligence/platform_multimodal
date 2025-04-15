#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json

from django.db import transaction, connections, IntegrityError
from rest_framework.decorators import action
from rest_framework.viewsets import GenericViewSet

from apps.sc_chat import sqls
from apps.sc_chat.models.chat_square_models import CCChatSquare, CCChatPrompt, CCChatMessages
from language.language_pack import RET
from utils.cst_class import CstResponse
from utils.generate_number import set_flow
from utils.model_save_data import ModelSaveData
from utils.sql_utils import dict_fetchall, NewSqlMixin
from utils.str_utils import get_random_data


class ChatSquare(NewSqlMixin, GenericViewSet):
    """
    问答广场 作者：xiaotao 版本号: 文档地址:
    """
    model_filter = ModelSaveData()
    query_sql = sqls.CHAT_SQUARE
    sort_field = ["a__id"]
    where = " and "
    lookup_field = "session_code"

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        for i in rows:
            i["session_data"] = json.loads(i["session_data"])
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    def retrieve(self, request, *args, **kwargs):
        session_code = self.kwargs[self.lookup_url_kwarg or self.lookup_field]
        rows = CCChatSquare.objects.filter(session_code=session_code, is_delete=0).values("question_code")
        if not rows:
            return CstResponse(RET.NO_DATE_ERROR)
        question_code = rows[0]["question_code"]
        question = CCChatPrompt.objects.filter(question_code=question_code).values("question_data")
        messages = CCChatMessages.objects.filter(session_code=session_code).values("session_data")

        resp = {
            "question_data": question[0]["question_data"],
            "session_data": messages[0]["session_data"],
            "session_code": session_code,
        }
        return CstResponse(RET.OK, data=resp)

    def create(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        session_data = data.get("session_data")
        session_code = data.get("session_code")
        question_data = data.get("question_data")
        module_id = data.get("module_id")
        question_id = data.get("question_id")
        if not all([session_data, session_code, question_data, module_id, question_id]):
            return CstResponse(RET.DATE_ERROR)
        for i in session_data:
            if "role" not in i or "content" not in i:
                return CstResponse(RET.DATE_ERROR)

        question_code = set_flow()
        save_data = self.model_filter.get_request_save_data(data, CCChatSquare)
        save_prompt_data = self.model_filter.get_request_save_data(data, CCChatPrompt)
        save_message_data = self.model_filter.get_request_save_data(data, CCChatMessages)

        save_data["question_code"] = question_code
        save_data["create_by"] = user.user_code
        save_prompt_data["question_code"] = question_code
        with transaction.atomic():
            try:
                CCChatSquare.objects.create(**save_data)
                CCChatPrompt.objects.create(**save_prompt_data)
                CCChatMessages.objects.create(**save_message_data)
            except IntegrityError:
                return CstResponse(RET.DATE_ERROR, "重复分享了！")

            except Exception as e:
                return CstResponse(RET.MAX_C_ERR)

        return CstResponse(RET.OK)

    def set_query_sql(self):
        query_sql = self.query_sql
        module_id = self.request.query_params.get('module_id')
        question_id = self.request.query_params.get('question_id')
        if module_id:
            query_sql += f" and a.module_id = '{module_id}'"
        if question_id:
            query_sql += f" and a.question_id = '{question_id}'"
        return query_sql

    @action(methods=["get"], detail=False)
    def rand_list(self, request, *args, **kwargs):
        data = request.query_params
        module_id = data.get("module_id")
        question_id = data.get("question_id")
        if not all([module_id, question_id]):
            return CstResponse(RET.DATE_ERROR)
        with connections["default"].cursor() as cursor:
            cursor.execute(sqls.CHAT_SQUARE_RAND, [module_id, question_id])
            rows = dict_fetchall(cursor)

        rows = get_random_data(rows, 5)
        for i in rows:
            i["session_data"] = json.loads(i["session_data"])
        return CstResponse(RET.OK, data=rows)
