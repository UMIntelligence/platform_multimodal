#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import requests
from django_redis import get_redis_connection
from requests.adapters import HTTPAdapter

from language.language_pack import RET
from utils.cst_class import CstException


def get_response(url, data=None, head=None, timeout=(10, 60), method="get", status=200):
    req = requests.Session()
    # req.mount('http://', HTTPAdapter(max_retries=2))
    # req.mount('https://', HTTPAdapter(max_retries=2))

    # 发送请求
    try:
        if method == "get":
            response = req.get(url, params=data, headers=head, timeout=timeout).json()
        elif method == "post":
            response = req.post(url, data=data, headers=head, timeout=timeout).json()
        elif method == "put":
            response = req.put(url, data=data, headers=head, timeout=timeout).json()
        else:
            raise CstException(RET.TP_ERR, status=status)
    except requests.exceptions.RequestException as e:
        raise CstException(RET.MAX_C_ERR, status=status)
    if response["code"] != 20000:
        # if response["code"] == 30014:
        #     status = 203
        raise CstException(response["code"], response["msg"], status=status)
    return response["data"]


def set_access_token(app_key, app_secret, redis_key, time_out=60 * 60 * 24 * 30):

    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={app_key}&client_secret={app_secret}"

    payload = ""
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    try:
        response = requests.post(url, data=payload, headers=headers).json()
    except Exception as e:
        return
    if response.get("error_code"):
        return
    redis_conn = get_redis_connection('config')
    redis_conn.set(redis_key, response["access_token"], ex=time_out)
