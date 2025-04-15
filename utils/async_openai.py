#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import logging
import openai
from asgiref.sync import sync_to_async

from django.db import transaction
from django_redis import get_redis_connection
from openai import OpenAI
from rest_framework import status

from apps.sc_chat.models.chat_models import OOpenaiKey
from language.language_pack import RET
from server_chat import settings
from utils import constants
from utils.cst_class import CstException
from utils.exponential_backoff import time_out, l_ip, async_retry_with_exponential_backoff_openai

# from tenacity import (
#     retry,
#     stop_after_attempt,
#     wait_random_exponential,
# )

logger = logging.getLogger(__name__)


class AsyncOpenAiUtils(object):
    model_list = constants.ModelList

    def __init__(self, request_id, chat_type, connect_timeout=10, read_timeout=60):
        self.request_id = request_id    # 监控用户是否违规
        self.timeout = (connect_timeout, read_timeout)        # 超时时间
        self.chat_type = chat_type
        # self.set_api_key()
        # openai.api_key = self.api_key

    def set_api_key(self):
        redis_conn = get_redis_connection('config')
        if self.chat_type in constants.GPT35:
            key = "35key_{}".format(l_ip)
            key_nx = "35key_{}_not_key".format(l_ip)
            base_key = "api_base_35"
        elif self.chat_type in constants.GPT40:
            key = "40key_{}".format(l_ip)
            key_nx = "40key_{}_not_key".format(l_ip)
            base_key = "api_base_40"
        else:
            raise CstException(RET.DATE_ERROR, "类型异常", status=309)
        api_key = redis_conn.get(key)
        if not api_key:
            is_set = redis_conn.set(key_nx, "", ex=time_out, nx=True)
            if not is_set:
                raise CstException(RET.DATE_ERROR, "正在部署key，请稍后重试", status=309)
            api_key = self.change_key(redis_conn)
        openai.api_key = api_key
        api_base = redis_conn.get(base_key) or None
        self.client = OpenAI(api_key=api_key, base_url=api_base)
        return

    def change_key(self, redis_conn):
        """更换备用key"""
        if self.chat_type in constants.GPT35:
            key_type = 0
            key = "35key_{}".format(l_ip)
        else:
            key = "40key_{}".format(l_ip)
            key_type = 1

        logger.info(l_ip)
        obj = OOpenaiKey.objects.filter(server_ip="", o_status=1, key_type=key_type).first()
        if not obj:
            raise CstException(RET.KEY_ERR, status=status.HTTP_303_SEE_OTHER)
        with transaction.atomic():
            OOpenaiKey.objects.filter(server_ip=l_ip, o_status=1, key_type=key_type).update(server_ip="", o_status=2)
            obj.server_ip = l_ip
            obj.save()
            redis_conn.set(key, obj.key)
        return obj.key

    @async_retry_with_exponential_backoff_openai
    async def acompletion_create(self, messages, model_index, max_tokens, stream=True, temperature=0.6, *args, **kwargs):

        model_engine = self.model_list[model_index]
        # try:
        completion = await sync_to_async(self.client.chat.completions.create)(  # 1. Change the function Completion to ChatCompletion
            model=model_engine,
            messages=messages,
            temperature=temperature,    # 调整散列分布，数值0-2，数值越大回答更加随机
            max_tokens=max_tokens,
            user=self.request_id,
            stream=stream,
            **kwargs
        )
        # except openai.error.OpenAIError as e:
        #     raise CstException(RET.TP_ERR, str(e.error), status=e.http_status)
        return completion

