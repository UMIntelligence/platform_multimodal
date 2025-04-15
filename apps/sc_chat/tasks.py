#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI

import requests
from django_redis import get_redis_connection

from server_chat import settings
from utils.request_utils import set_access_token


def test_chat():
    url = settings.SERVER_OPENAI_URL + "api/server_openai/test"
    try:
        result = requests.get(url, timeout=10).json()
    except Exception as e:
        pass


def set_ernie_access_token():
    # 绘画语音
    redis_conn = get_redis_connection('config')
    ernie_ak = redis_conn.get("ERNIE_APP_KEY")
    ernie_sk = redis_conn.get("ERNIE_APP_SECRET")

    set_access_token(ernie_ak, ernie_sk, "baidu_ernie")


def set_chat_ernie_access_token():
    # 对话
    redis_conn = get_redis_connection('config')
    chat_ak = redis_conn.get("ERNIE_CHAT_APP_KEY")
    chat_sk = redis_conn.get("ERNIE_CHAT_APP_SECRET")
    set_access_token(chat_ak, chat_sk, "baidu_chat_ernie")


# def set_baidu_voice_access_token():
#     set_access_token(settings.B_APP_KEY, settings.BV_TTS_APP_SECRET, "baidu_voice_ernie")


