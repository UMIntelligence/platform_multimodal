#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import base64
import json
import logging
import time
from abc import ABC, abstractmethod

import requests
from django_redis import get_redis_connection

from language.language_pack import RET
from server_chat import settings
from utils.cst_class import CstException, ImageException
from utils.mq_utils import RabbitMqUtil

logger = logging.getLogger(__name__)
time_out = 60


class LogicalStrategyABC(ABC):

    @abstractmethod
    def send_data(self, *args, **kwargs):
        pass


class OpenaiDall(LogicalStrategyABC):

    def send_data(self, *args, **kwargs):
        data = kwargs["data"]
        files = kwargs["files"]
        url = settings.SERVER_OPENAI_URL + "api/server_openai/generation_image"
        try:
            result = requests.post(url, data=data, files=files, timeout=time_out)
            result = result.json()
        except Exception as e:
            raise CstException(RET.SERVER_ERROR, str(e))

        if result["code"] != 20000:
            raise CstException(RET.DATE_ERROR, json.loads(result["msg"])["message"])
        image_urls = result["data"]["data"]
        return image_urls

    def asend_data(self, *args, **kwargs):
        data = kwargs["data"]
        files = kwargs["files"]
        url = settings.SERVER_OPENAI_URL + "api/server_openai/async_generation_image"
        try:
            result = requests.post(url, data=data, files=files, timeout=time_out)
            result = result.json()
        except Exception as e:
            raise CstException(RET.SERVER_ERROR, str(e))

        if result["code"] != 20000:
            raise CstException(RET.DATE_ERROR, json.loads(result["msg"])["message"])
        image_urls = result["data"]["data"]
        return image_urls

    def get_data(self, data):
        pass


class StableDiffusionImage(LogicalStrategyABC):
    realm_name = settings.SD_HOST
    rabbit_mq = RabbitMqUtil()

    def get_data(self, request, *args, **kwargs):
        tag = kwargs["tag"]
        user = request.user
        data = request.data
        source = user.source
        role = user.role
        user_code = user.user_code
        # action_type = data.get("action_type")  # 行为,3:生成图片，,5,图片编
        # app_type = data.get("app_type") or 1  # 1:通用，2四维
        # chat_type = data.get("chat_type")  # or "9"
        size = data.get("size") or "512*512"  #
        size_list = size.split("*")
        if len(size_list) != 2:
            raise CstException(RET.DATE_ERROR, "尺寸错误")

        data["user_code"] = user_code
        data["source"] = source
        data["role"] = role
        data["task_id"] = tag
        data["msg_code"] = tag
        return data

    def send_data(self, request, *args, **kwargs):
        request_data = self.get_data(request, **kwargs)
        data = {
            'exchange': "sd_exchange",
            'queue': "sd_query",
            'routing_key': 'StableDiffusion',
            'type': "direct",
            "msg": request_data
        }
        self.rabbit_mq.send_handle(data)
        return
