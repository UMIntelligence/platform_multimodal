#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json

from django.core.management import BaseCommand

from sv_voice.models.text_to_speech_models import VtTextToSpeechEngine
from utils import constants, tts_strategy
from utils.connections_utils import handle_db_connections
from utils.mq_utils import RabbitMqUtil


class Command(BaseCommand):
    rabbit_mq = RabbitMqUtil()

    def handle(self, *args, **options):
        data = {
            'exchange': constants.EXCHANGE,
            'queue': "tts_query",
            'routing_key': 'tts_result',
            'type': "direct",
            'callback': self.callback_func,
            'delay': {
                'exchange': constants.EXCHANGE,
                'queue': 'tts_query_delay',
                'routing_key': 'tts_result_delay',
            }
        }
        self.rabbit_mq.bin_handle(data)

    @handle_db_connections
    @rabbit_mq.handel_error
    def callback_func(self, ch, method, properties, body):
        message = json.loads(body)
        print(message)
        engine_code = message["engine_code"]
        action_type = message["action_type"]
        engine = VtTextToSpeechEngine.objects.filter(engine_code=engine_code).first()

        obj = getattr(tts_strategy, engine.class_name)(create_by=message["create_by"], engine=engine, action_type=action_type)

        obj.tts_result(message)

        print("------------完成---------")
