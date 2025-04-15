#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import datetime
import json
import logging

from asgiref.sync import sync_to_async
from django.db import connections, transaction
from django.forms import model_to_dict
from django.http import StreamingHttpResponse
from django_redis import get_redis_connection
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from language.language_pack import RET
from sc_chat import sqls
from apps.sc_chat.models.group_chat_model import CgChatRole, CgGroupChat, CgGroupChatRole, CgGroupChatDtl
from sc_chat.utils import check_members
from utils import constants, chat_strategy
from utils.ali_sdk import ali_client
from utils.cst_class import CstResponse
from utils.generate_number import set_flow
from utils.generics import AsyncGenericAPIView
from utils.model_save_data import ModelSaveData
from utils.num_tokens import num_tokens_from_messages, split_messages
from utils.redis_lock import AsyncLockRequest
from utils.sql_utils import NewSqlMixin, dict_fetchall

logger = logging.getLogger(__name__)


class GetModel(APIView):
    """
    获取模型
    """
    def get(self, request):
        redis_conn = get_redis_connection("model")
        model_info = redis_conn.hget("hashrateRules", "pricing")
        model_info = json.loads(model_info)
        rsp = [i for i in model_info if i["chat_type"] in constants.GROUP_TYPE]

        return CstResponse(RET.OK, data=rsp)


class ChatRoleView(NewSqlMixin, GenericViewSet):
    """
    角色视图 作者：xiaotao 版本号: 文档地址: http://124.70.221.169:5000/web/#/9/82
    """
    sort_field = ["create_time"]
    sort_type = "desc"
    where = " and "
    query_sql = sqls.ChatRoleList
    model_filter = ModelSaveData()

    def set_query_sql(self):
        user_code = self.request.user.user_code
        role_type = self.request.query_params.get("role_type")
        self.query_sql += f" and create_by = '{user_code}'"
        if role_type:
            self.query_sql += f" and role_type = {role_type}"

        return self.query_sql

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    def retrieve(self, request, role_code, *args, **kwargs):
        obj = CgChatRole.objects.filter(role_code=role_code).first()
        if not obj:
            return CstResponse(RET.DATE_ERROR, "未找到")
        data = model_to_dict(obj)
        return CstResponse(RET.OK, data=data)

    def create(self, request, *args, **kwargs):
        user_code = request.user.user_code
        data = request.data
        if not all([data.get("chat_type"), data.get("model")]):
            return CstResponse(RET.DATE_ERROR)
        exclude = ["id", "role_type"]
        save_data = self.model_filter.get_request_save_data(data, CgChatRole, exclude=exclude)
        save_data["create_by"] = user_code
        save_data["role_code"] = set_flow()
        obj = CgChatRole.objects.create(**save_data)
        return CstResponse(RET.OK, data=model_to_dict(obj))

    def update(self, request, role_code, *args, **kwargs):
        data = request.data
        exclude = ["id", "role_type", "role_code"]
        save_data = self.model_filter.get_request_save_data(data, CgChatRole, exclude=exclude)
        CgChatRole.objects.filter(role_code=role_code, role_type=2).update(**save_data)
        return CstResponse(RET.OK)

    def destroy(self, request, role_code, *args, **kwargs):
        obj = CgChatRole.objects.filter(role_code=role_code).first()
        if obj.role_type == 1:
            return CstResponse(RET.DATE_ERROR, "通用角色不允许删除没只允许解绑")
        obj.delete()
        return CstResponse(RET.OK)


class GroupChatView(NewSqlMixin, GenericViewSet):
    """
    对话视图 作者：xiaotao 版本号: 文档地址: http://124.70.221.169:5000/web/#/9/82
    """
    sort_field = ["create_time"]
    sort_type = "desc"
    where = " and "
    query_sql = sqls.GroupChatList
    model_filter = ModelSaveData()

    def set_query_sql(self):
        user_code = self.request.user.user_code
        title = self.request.query_params.get("title")
        self.query_sql += f" and create_by = '{user_code}'"
        if title:
            self.query_sql += f" and title like '{title}%'"

        return self.query_sql

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    def retrieve(self, request, session_code, *args, **kwargs):
        with connections["default"].cursor() as cursor:
            cursor.execute(sqls.GroupChatDtl, [session_code])
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data=rows)

    def create(self, request, *args, **kwargs):
        user = request.user
        source = user.source
        user_code = user.user_code
        data = request.data
        model_list = data.get("model_list")
        subject = data.get("subject")
        total_integral = data.get("total_integral")
        if not all([total_integral, model_list, subject]) or not isinstance(model_list, list):
            return CstResponse(RET.DATE_ERROR)

        exclude = ["id", "session_code"]
        save_data = self.model_filter.get_request_save_data(data, CgGroupChat, exclude=exclude)
        dtl_save_data = self.model_filter.get_request_save_data(model_list, CgGroupChatRole, exclude=["id"])
        save_data["session_code"] = set_flow()
        save_data["create_by"] = user_code
        save_data["source"] = source
        save_data["title"] = subject[:15] + "..."
        save_data["use_integral"] = total_integral

        insert_list = []
        with transaction.atomic():
            obj = CgGroupChat.objects.create(**save_data)
            for dtl in dtl_save_data:
                dtl["session_code"] = obj.session_code
                dtl["group_role_code"] = set_flow()
                dtl["create_by"] = user_code
                insert_list.append(CgGroupChatRole(**dtl))
            CgGroupChatRole.objects.bulk_create(insert_list)

        with connections["default"].cursor() as cursor:
            cursor.execute(sqls.GroupChatRole, [obj.session_code])
            rows = dict_fetchall(cursor)

        return CstResponse(RET.OK, data={"session_code": obj.session_code, "model_list": rows})

    def update(self, request, session_code, *args, **kwargs):
        data = request.data
        use_integral = data.get("use_integral") or 0
        obj = CgGroupChat.objects.filter(session_code=session_code).first()
        if not obj:
            return CstResponse(RET.DATE_ERROR, "未找到")
        obj.total_integral += use_integral
        obj.use_integral += use_integral
        obj.save()

        return CstResponse(RET.OK)

    def destroy(self, request, session_code, *args, **kwargs):
        obj = CgGroupChat.objects.filter(session_code=session_code).first()
        if not obj:
            return CstResponse(RET.DATE_ERROR, "未找到")
        with transaction.atomic():
            CgGroupChatRole.objects.filter(session_code=session_code).delete()
            CgGroupChatDtl.objects.filter(session_code=session_code).delete()
            obj.delete()
        return CstResponse(RET.OK)


class AsyncGroupChatCompletion(AsyncGenericAPIView):
    """
    群聊会话视图 作者：xiaotao 版本号: 文档地址: http://124.70.221.169:5000/web/#/9/82
    """
    chat_type_map = {
        "4": "ChatErnieBotTurbo",       # 文心一言
        "5": "ChatSpark",               # 科大讯飞
        "8": "ChatGLM",               # GLM
        "10": "QwEn",               # 千问
        "12": "QihooChat",               # 360智脑
    }

    @AsyncLockRequest()
    async def post(self, request):
        user = request.user
        data = request.data
        create_by = user.user_code
        session_code = data.get("session_code")
        group_role_code = data.get("group_role_code") or ""
        msg_list = data.get("msg_list")  # 提问
        status = 400
        if not all([session_code, msg_list]) or not isinstance(msg_list, list):
            return CstResponse(RET.DATE_ERROR)

        _ = check_members(create_by, status=status)

        g_obj = await CgGroupChat.objects.filter(session_code=session_code, create_by=create_by).afirst()
        if not g_obj:
            return CstResponse(RET.DATE_ERROR, "话题未找到", status=status)
        role_chat_obj = await CgGroupChatRole.objects.filter(group_role_code=group_role_code).afirst()
        if role_chat_obj:
            # 获取角色和模型
            role_code = role_chat_obj.role_code
            role_obj = await CgChatRole.objects.filter(role_code=role_code).afirst()
            chat_type = str(role_obj.chat_type)
            model = role_obj.model
        else:
            chat_type = str(data.get("chat_type") or "4")
            model = data.get("model")
        use_integral = g_obj.use_integral

        if use_integral <= 0:
            return CstResponse(RET.INTEGRAL_ERROR, status=status)

        if chat_type not in self.chat_type_map.keys():
            return CstResponse(RET.DATE_ERROR, status=status)

        obj = getattr(chat_strategy, self.chat_type_map[chat_type])(model=model, chat_type=chat_type)
        send_list = self.get_send_msg(msg_list)
        # print(send_list)
        send_list = split_messages(send_list)   # 超长截取
        # print(send_list)

        request_data = obj.get_data(request, msg_list=send_list, create_by=create_by)
        if chat_type in ["5", "7", "8"]:
            resp = await obj.create(request_data, status=status)
        else:
            resp = await sync_to_async(obj.create)(request_data, status=status)

        save_data = msg_list[-1:][0]
        save_data["session_code"] = session_code
        save_data["group_role_code"] = group_role_code
        save_data["create_by"] = create_by
        save_data["msg_code"] = set_flow()
        save_data["chat_type"] = chat_type
        save_data["model"] = model

        response = StreamingHttpResponse(obj.group_save(
            resp, save_data=save_data, request_data=data
        ), content_type='text/event-stream; charset=utf-8')
        response['Cache-Control'] = 'no-cache'
        print("-------11111")
        return response

    @staticmethod
    def get_send_msg(msg_list):
        send_list = []
        for i in msg_list:
            covert_content = i.get("covert_content") or ""
            send_list.append({"role": i["role"], "content": covert_content + i["content"]})
        return send_list
