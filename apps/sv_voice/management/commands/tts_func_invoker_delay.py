#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json

from django.core.management import BaseCommand

from sv_voice.models.text_to_speech_models import VtTextToSpeechEngine, VtTextToSpeechHistory
from utils import constants, tts_strategy
from utils.connections_utils import handle_db_connections
from utils.mq_utils import RabbitMqUtil


class Command(BaseCommand):
    rabbit_mq = RabbitMqUtil()

    def handle(self, *args, **options):
        data = {
            'exchange': constants.EXCHANGE,
            'queue': 'tts_query_delay',
            'routing_key': 'tts_result_delay',
            'type': "direct",
            'callback': self.callback_func,
        }
        self.rabbit_mq.bin_handle(data)

    @handle_db_connections
    @rabbit_mq.ack_err
    def callback_func(self, ch, method, properties, body):
        message = json.loads(body)
        print(message)
        engine_code = message["engine_code"]
        h_code = message["h_code"]
        action_type = message["action_type"]
        engine = VtTextToSpeechEngine.objects.filter(engine_code=engine_code).first()

        obj = getattr(tts_strategy, engine.class_name)(action_type=action_type)

        try:
            obj.tts_result(message)
        except Exception as e:
            VtTextToSpeechHistory.objects.filter(h_code=h_code).update(
                h_status=3,
            )

        print("------------完成---------")
