#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from sv_voice.models.speech_models import SpeechRecognitionHistory
from sv_voice.serializers.base_serializers import BaseModelSerializer
from utils.generate_number import set_flow


class CreateCheckSpeech:
    @staticmethod
    def execute(validated_data):
        speech_code = set_flow()
        validated_data["speech_code"] = speech_code
        return validated_data


class UpdateCheckSpeech:
    @staticmethod
    def execute(validated_data, instance=None):
        validated_data.pop('speech_code', None)
        return validated_data


class SpeechRecognitionSerializer(BaseModelSerializer):
    """

    """
    create_cst = CreateCheckSpeech()
    update_cst = UpdateCheckSpeech()

    class Meta:
        model = SpeechRecognitionHistory
        fields = '__all__'
