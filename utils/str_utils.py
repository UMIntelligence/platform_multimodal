#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI

import base64
import json
import random
import re

import requests
from django_redis import get_redis_connection

from language.language_pack import RET
from server_chat import settings
from utils.ali_sdk import ali_client, ocr_recognize
from utils.cst_class import CstException


def string_to_base64(input_string):
    # 将字符串编码为字节流
    input_bytes = input_string.encode('utf-8')

    # 使用base64进行编码
    encoded_bytes = base64.b64encode(input_bytes)

    # 将字节流转换为字符串
    encoded_string = encoded_bytes.decode('utf-8')

    return encoded_string


def url_to_base64(url):
    try:
        response = requests.get(url)
    except Exception as e:
        raise CstException("网络异常，图片访问失败!")
    image_content = response.content
    base64_string = base64.b64encode(image_content)
    return base64_string.decode('utf-8')


def base64_to_binary(base64_data):
    binary_data = base64.b64decode(base64_data)
    return binary_data


def get_suffix(url, suffix="png"):
    match = re.search(r'\.([^.]*?)(?:\?|$)', url)
    if match:
        suffix = match.group(1)
    else:
        suffix = suffix
    return suffix


def get_random_data(data_list, num):
    if num > len(data_list):
        num = len(data_list)
    random_data = random.sample(data_list, num)
    return random_data


def ali_text_mod_func(content):
    is_mod = 0
    mod_text = ""
    if len(content) < 600:
        try:
            _ = ali_client.ali_text_mod(json.dumps({"content": content}, ensure_ascii=False))
        except CstException as e:
            is_mod = 1
            mod_text = "回答内容涉及敏感字眼，请重新提问。"
    return is_mod, mod_text


def key_from_dicts(dicts: list, key_list: list = ["role", "content"]) -> list:
    return [{k: v for k, v in d.items() if k in key_list} for d in dicts]


def get_send_msg(msg_list):
    send_list = []
    r = get_redis_connection("prompts")
    for i in msg_list:
        covert_content = i.get("covert_content") or ""
        content_type = i.get("content_type") or ""
        origin_image = i.get("origin_image") or ""
        agent_id = i.get("agent_id")
        image_content = ""
        images = i.get("images") or []
        if len(images) >= 2:
            raise CstException(RET.DATE_ERROR)
        for image in images:
            image_content = ocr_recognize.recognize_general(settings.NETWORK_STATION + image).get("content", "")
            image_content += "\r\n"
            # image_content += "。如下内容是我通过图片识别的出的内容，按照我上面的提问给出答案："
            image_content += image_content
            image_content += "\r\n"

        if agent_id:
            try:
                covert_content = json.loads(r.hget("agent", agent_id)).get("prompts")
            except Exception as e:
                covert_content = ""
            i["covert_content"] = covert_content
        text_dict = {"role": i["role"], "content": covert_content + i["content"] + image_content}
        # print(text_dict)
        if content_type:
            text_dict["content_type"] = content_type
        if origin_image:
            text_dict["origin_image"] = origin_image
        send_list.append(text_dict)
    return send_list
