#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json
import logging

from django.core.management import BaseCommand

from sc_chat.utils import get_dell_model, deduction_calculation
from utils import constants, image_strategy
from utils.connections_utils import handle_db_connections
from utils.generate_number import set_flow
from utils.mq_utils import RabbitMqUtil
from utils.save_utils import save_image_v2

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    rabbit_mq = RabbitMqUtil()
    chat_type_map = constants.FILE_CHAT_TYPE

    def handle(self, *args, **options):
        data = {
            'exchange': "image_exchange_delay",
            'queue': 'image_query_delay',
            'routing_key': 'image_generate_delay',
            'type': "direct",
            'callback': self.callback_func,
        }
        self.rabbit_mq.bin_handle(data)

    @handle_db_connections
    @rabbit_mq.ack_err
    def callback_func(self, ch, method, properties, body):
        data = json.loads(body)
        print(data)
        user_code = data["user_code"]
        chat_type = data["chat_type"]
        model = data.get("model") or ""

        result_list = [data]

        class_name = self.chat_type_map[chat_type]
        logger.info(f"""{class_name}---------{data}""")

        obj = getattr(image_strategy, class_name)(model=model, chat_type=chat_type)
        try:
            number = obj.result_query(data, result_list, mq_obj=self.rabbit_mq.mq_obj)
        except Exception as e:
            result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
            number = "0"

        for save_result in result_list[1:]:
            if save_result.get("status", 0) != 1:
                model_c = get_dell_model(data)
                integral = deduction_calculation(chat_type, number, model_c)
                save_result["integral"] = integral
            save_result["role"] = "assistant"
        _ = save_image_v2(data, result_list, user_code)

        logger.info(f"""{class_name}---------生成成功""")
