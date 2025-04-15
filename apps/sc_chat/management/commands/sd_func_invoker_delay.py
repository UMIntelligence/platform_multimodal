#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json

from django.core.management import BaseCommand

from apps.sc_chat.management.commands.sd_func_invoker import create_img, ultrasound, get_req_data
from sc_chat.utils import deduction_calculation
from server_chat import settings
from utils.connections_utils import handle_db_connections
from utils.mq_utils import RabbitMqUtil
from utils.save_utils import save_image_v2
from utils.str_utils import url_to_base64


class Command(BaseCommand):
    rabbit_mq = RabbitMqUtil()

    def handle(self, *args, **options):
        data = {
            'exchange': "sd_exchange_delay",
            'queue': "sd_func_invoker_delay",
            'routing_key': 'sd_func_invoker_delay',
            'type': "direct",
            'callback': self.callback_func,
        }
        self.rabbit_mq.bin_handle(data)

    @handle_db_connections
    @rabbit_mq.ack_err
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

            if app_type == "2":  # 四维彩超
                ultrasound(req_data, result_list, message, is_delay=1)
            else:
                create_img(req_data, result_list, message, is_delay=1)
        else:
            create_img(req_data, result_list, message, is_delay=1)

        for save_result in result_list[1:]:
            if save_result.get("status", 0) != 1:
                integral = deduction_calculation(chat_type, 1)
                save_result["integral"] = integral
            save_result["role"] = "assistant"
        _ = save_image_v2(message, result_list, user_code)
        print("--------")
