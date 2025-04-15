#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import base64
import io
import json
import random

import requests
from django.core.management import BaseCommand
from django.db import transaction
from django_redis import get_redis_connection

from apps.sc_chat.utils import charges_api, deduction_calculation
from language.language_pack import RET
from server_chat import settings
from utils import constants
from utils.ali_sdk import ali_client, get_oss_url, ImageScore
from utils.connections_utils import handle_db_connections
from utils.cst_class import CstException
from utils.generate_number import set_flow
from utils.mq_utils import RabbitMqUtil
from utils.save_utils import save_image_task, save_image_v2
from utils.sso_utils import ToOss
from utils.str_utils import url_to_base64


class Command(BaseCommand):
    rabbit_mq = RabbitMqUtil()

    def handle(self, *args, **options):
        data = {
            'exchange': "sd_exchange",
            'queue': "sd_query",
            'routing_key': 'StableDiffusion',
            'type': "direct",
            'callback': self.callback_func,
            'delay': {
                'exchange': "sd_exchange_delay",
                'queue': 'sd_func_invoker_delay',
                'routing_key': 'sd_func_invoker_delay',
            }
        }
        self.rabbit_mq.bin_handle(data)

    @handle_db_connections
    @rabbit_mq.handel_error
    def callback_func(self, ch, method, properties, body):
        message = json.loads(body)
        print(message)
        req_data = get_req_data(message)
        user_code = message["user_code"]
        action_type = message.get("action_type", "")
        chat_type = message.get("chat_type", "")
        app_type = message.get("app_type") or "1"

        result_list = [message]

        if action_type == "5":
            init_images = []
            images = req_data.get("images")
            for image in images:
                image_url = settings.NETWORK_STATION + image
                init_images.append(url_to_base64(image_url))
            req_data["init_images"] = init_images

            if app_type == "2":   # 四维彩超
                ultrasound(req_data, result_list, message)
            else:
                create_img(req_data, result_list, message)
        else:
            create_img(req_data, result_list, message)

        for save_result in result_list[1:]:
            if save_result.get("status", 0) != 1:
                integral = deduction_calculation(chat_type, 1)
                save_result["integral"] = integral
            save_result["role"] = "assistant"
        _ = save_image_v2(message, result_list, user_code)
        print("--------")


def get_req_data(data):
    action_type = data.get("action_type")  # 行为,3:生成图片，,5,图片编
    size = data.get("size") or "512*512"  # 反向提示词
    size_list = size.split("*")
    prompt_en = data.get("prompt_en") or ""
    negative_prompt_en = data.get("negative_prompt_en") or ""  # 反向提示词
    payload = {
        'prompt': prompt_en,
        # 提示词
        'negative_prompt': negative_prompt_en,  # 反向提示词
        # "Model": "anything-v5-PrtRE",
        # "override_settings": {"sd_model_checkpoint": "anything-v5-PrtRE"},
        "override_settings": {
            "sd_model_checkpoint": data.get("model") or "anything-v5-PrtRE",
            # "sd_vae": "",
        },
        'sampler_index': data.get("sampler_index") or "Euler a",
        'seed': data.get("seed") or -1,  # 随机种子
        'steps': data.get("steps") or 20,  # 迭代步数
        'width': size_list[0],
        'height': size_list[1],
        'cfg_scale': data.get("cfg_scale") or 7,  # 提示词相关性
        'version': "v1.5.1",
        'denoising_strength': 0.75
    }
    if action_type == "5":
        origin_image = data.get("origin_image")
        payload["images"] = [origin_image]
    return payload


def create_img(payload, result_list, message, *args, **kwargs):
    is_delay = kwargs.get("is_delay", None)
    realm_name = settings.SD_HOST
    action_type = message["action_type"]
    payload_json = json.dumps(payload)
    if action_type == "5":
        url_image = "img2img"
    else:
        url_image = "txt2img"
    try:
        response = requests.post(url=f'{realm_name}sdapi/v1/{url_image}', data=payload_json, timeout=(10, 120)).json()
    except Exception as e:
        if not is_delay:
            raise CstException(RET.MAX_C_ERR)
        result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
        return
    if isinstance(response, dict) and response.get("error"):
        if not is_delay:
            raise CstException(RET.MAX_C_ERR)
        result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
        return
    init = ToOss()
    # print(response)
    for i in response['images']:
        sso_url = init.main("sd", file_con=io.BytesIO(base64.b64decode(i)))
        s_url = settings.NETWORK_STATION + sso_url
        print(s_url)
        is_mod = 0
        try:
            _ = ali_client.ali_image_mod(s_url)
        except CstException as e:
            init.delete_object(sso_url)
            is_mod = 1
            sso_url = ""
        result_dict = dict()
        result_dict["result_image"] = sso_url
        result_dict["msg_code"] = set_flow()
        result_dict["task_id"] = message["task_id"]
        result_dict["is_mod"] = is_mod
        result_list.append(result_dict)
    return


def ultrasound(req_data, result_list, message, *args, **kwargs):
    width = req_data.get("width")
    height = req_data.get("height")

    s_obj = ImageScore()
    for index in range(2):
        create_img(req_data, result_list, message, *args, **kwargs)
        url_dict = result_list.pop()
        sso_url = url_dict["result_image"]
        is_mod = url_dict.get("is_mod") or 0
        status_image = url_dict.get("status") or 0
        if status_image != 1 and is_mod != 1:
            try:
                sso_url = settings.NETWORK_STATION + sso_url
                oss_url = get_oss_url(sso_url)
                score = s_obj.score_run(oss_url)
                print(score, "-----------")
                if score <= 3.62:
                    if index == 1:
                        redis_conn = get_redis_connection('chat')
                        sd_ultrasound = json.loads(redis_conn.get("sd_ultrasound"))
                        size = str(width) + "*" + str(height)
                        url = random.choices(sd_ultrasound, k=1)[0].get(size)  # 抄了就随机取
                        url_dict["result_image"] = url
                        result_list.append(url_dict)
                else:
                    result_list.append(url_dict)
                    return
            except Exception as e:
                result_list.append(url_dict)
                return
