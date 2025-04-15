#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json
import logging

from django.db import transaction, connections
from django_redis import get_redis_connection
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.sc_chat import sqls
from apps.sc_chat.models.chat_models import CCChatSessionDtl, CCChatSession
from apps.sc_chat.tasks import set_chat_ernie_access_token
from language.language_pack import RET
from server_chat import settings
from utils.ali_sdk import ali_client
from utils.cst_class import CstResponse
from utils.sql_utils import dict_fetchall, NewSqlMixin

logger = logging.getLogger(__name__)


class Test(APIView):
    """"""
    authentication_classes = []

    def post(self, request):
        # set_chat_ernie_access_token()
        url = "https://umi-intelligence.oss-cn-shenzhen.aliyuncs.com/chat/sd/f0e2f93e-cce8-413f-b8f7-828662bf2de3.png"
        url = "https://umi-intelligence.oss-cn-shenzhen.aliyuncs.com/chat/sd/e7a3a6dd-a25e-458e-a42f-9c6010ee5ea2.png"
        url = "https://umi-intelligence.oss-cn-shenzhen.aliyuncs.com/static/picture/bf0ce7f8-7afb-4ee1-a7cf-fd3450008cdb.jpg"
        _ = ali_client.ali_image_mod(url)
        print(_)
        return CstResponse(RET.OK)


class GetACToken(APIView):
    authentication_classes = []

    def get(self, request):
        redis_conn = get_redis_connection('default')
        access_token = redis_conn.get("baidu_chat_ernie")
        access_token = access_token.decode("utf-8")
        return CstResponse(RET.OK, data=access_token)


class Webhook(APIView):
    authentication_classes = []

    def post(self, request):
        data = request.data
        logger.info(data)
        print(str(data))
        return CstResponse(RET.OK)


class ChatView(ViewSet, NewSqlMixin):
    """

    """
    query_sql = sqls.CHAT_LIST_SQL
    sort_field = ["a__create_time"]
    # main_table = "a"
    where = " and "

    def set_query_sql(self):
        query_sql = self.query_sql
        title = self.request.query_params.get('title')
        chat_type = self.request.query_params.get('chat_type')
        question_id = self.request.query_params.get('question_id')
        is_question = self.request.query_params.get('is_question')
        company_code = self.request.query_params.get('company_code')
        clerk_code = self.request.query_params.get('clerk_code')
        scenario_type = self.request.query_params.get('scenario_type') or ""
        create_by = self.request.user.user_code
        if title:
            query_sql += f" and a.title like '{title}%'"
        if create_by:
            query_sql += f" and a.create_by = '{create_by}'"
        if chat_type:
            if not company_code:
                query_sql += f" and chat_type = {chat_type} and b.company_code is null"
            else:
                query_sql += f" and chat_type = {chat_type}"
        if question_id:
            query_sql += f" and a.question_id = '{question_id}'"
        if is_question:
            query_sql += " and a.question_id != ''"
        if company_code:
            query_sql += f" and b.company_code = '{company_code}'"
        if clerk_code:
            query_sql += f" and b.clerk_code = '{clerk_code}'"
        query_sql += f" and scenario_type = '{scenario_type}'"

        return query_sql

    def list(self, request, *args, **kwarg):
        """
        会话框列表视图
        :param request:
        :param args:
        :param kwarg:
        :return:
        """
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        is_question = request.query_params.get('is_question')   # 是否名人
        if is_question and rows:
            q_rows = self.question_query(rows)
            for i in rows:
                for j in q_rows:
                    if i["question_id"] == str(j["question_id"]):
                        i.update(j)

        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    def question_query(self, rows):
        question_ids = list(set([i["question_id"] for i in rows]))
        if len(question_ids) == 1:
            question_ids = "(" + question_ids[0] + ")"
        else:
            question_ids = "(" + ",".join(question_ids) + ")"
        with connections["admin"].cursor() as cursor:
            sql = sqls.QuestionSql + f" and question_id in {question_ids}"
            cursor.execute(sql)
            q_rows = dict_fetchall(cursor)
        return q_rows

    def retrieve(self, request, session_code, *args, **kwargs):
        """
        会话详情视图
        :param request:
        :param session_code:
        :param args:
        :param kwargs:
        :return:
        """
        user = request.user
        create_by = user.user_code
        sql = sqls.CHAT_RETRIEVE_SQL
        with connections["default"].cursor() as cursor:
            cursor.execute(sql, [session_code, create_by])

            rows = dict_fetchall(cursor)
        # resp = []
        #
        # chat_group_code_list = []
        for i in rows:
            if i["images"]:
                i["images"] = json.loads(i["images"])
        #     new_dict = {"chat_group_code": i["chat_group_code"], "info": []}
        #     if new_dict not in chat_group_code_list:
        #         chat_group_code_list.append(new_dict)
        #
        # for chat_group in chat_group_code_list:
        #     for d in rows:
        #         if chat_group["chat_group_code"] == d["chat_group_code"]:
        #             chat_group["action_type"] = d["action_type"]  # 取最后的类型
        #             chat_group["info"].append(d)
        #     resp.append(chat_group)

        return CstResponse(RET.OK, data=rows)

    def destroy(self, request, *args, **kwargs):
        """
        会话删除
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        user = request.user
        create_by = user.user_code
        session_codes = request.query_params.get("session_codes")
        session_codes = json.loads(session_codes)

        with transaction.atomic():
            CCChatSession.objects.filter(session_code__in=session_codes, create_by=create_by).update(is_delete=1)
            CCChatSessionDtl.objects.filter(session_code__in=session_codes, create_by=create_by).update(is_delete=1)
        return CstResponse(RET.OK)

    @action(methods=["delete"], detail=False)
    def destroy_all(self, request, *args, **kwargs):
        user = request.user
        create_by = user.user_code

        with transaction.atomic():
            CCChatSession.objects.filter(create_by=create_by).delete()
            CCChatSessionDtl.objects.filter(create_by=create_by).delete()
        return CstResponse(RET.OK)

    @action(methods=["put"], detail=False)
    def chat_likes(self, request, *args, **kwargs):
        """
        聊天点赞
        """
        data = request.data
        is_likes = data.get("is_likes")  # 行为,0:取消，1：点赞，2：点踩
        session_code = data.get("session_code")
        chat_group_code = data.get("chat_group_code")
        if not all([is_likes, session_code, chat_group_code]):
            return CstResponse(RET.DATE_ERROR)

        CCChatSessionDtl.objects.filter(session_code=session_code, chat_group_code=chat_group_code).update(
            is_likes=is_likes
        )

        return CstResponse(RET.OK)

    @action(methods=["put"], detail=False)
    def update_title(self, request, *args, **kwargs):
        user = request.user
        create_by = user.user_code
        session_code = request.data.get("session_code")
        title = request.data.get("title", "")
        CCChatSession.objects.filter(session_code=session_code, create_by=create_by).update(title=title)
        return CstResponse(RET.OK)
