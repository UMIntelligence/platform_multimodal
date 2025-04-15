#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import transaction
from rest_framework import serializers

from language.language_pack import RET
from sv_voice.models.digital_human_models import DigitalHumanExperience, DigitalHumanFile, DigitalHumanLiveVideo, \
    DigitalHumanCustomizedVoice, DigitalHumanProject
from sv_voice.models.exchange_models import DigitalHumanActivateNumber, DigitalHumanActivateConsumeHistory
from sv_voice.serializers.base_serializers import BaseModelSerializer
from utils.cst_class import CstException
from utils.generate_number import set_flow


class CreateCheckHuman:
    @staticmethod
    def execute(validated_data):
        mobile = validated_data.get("mobile")
        if not mobile:
            raise CstException(RET.DATE_ERROR, "请填写联系方式")
        return validated_data


class DigitalHumanExperienceSerializer(BaseModelSerializer):
    """

    """
    create_cst = CreateCheckHuman()

    class Meta:
        model = DigitalHumanExperience
        fields = '__all__'


class CreateCheckFile:
    @staticmethod
    def execute(validated_data):
        file_code = set_flow()
        validated_data["file_code"] = file_code
        return validated_data


class DigitalHumanFileSerializer(BaseModelSerializer):
    """

    """
    create_cst = CreateCheckFile()

    class Meta:
        model = DigitalHumanFile
        fields = '__all__'


class CreateCheckClone:
    @staticmethod
    def execute(validated_data):
        power_attorney_url = validated_data.get("power_attorney_url")
        live_video_url = validated_data.get("live_video_url")
        if not all([power_attorney_url, live_video_url]):
            raise CstException(RET.DATE_ERROR)
        live_code = set_flow()
        validated_data["live_code"] = live_code
        validated_data["live_video_code"] = "dhc" + live_code + ".mp4"
        return validated_data


class UpdateCheckClone:
    @staticmethod
    def execute(validated_data, instance=None):
        if instance.make_status != 1:
            raise CstException(RET.DATE_ERROR, "只有草稿状态可以修改")
        return validated_data


class DigitalHumanCloneSerializer(BaseModelSerializer):
    """

    """
    create_cst = CreateCheckClone()
    update_cst = UpdateCheckClone()

    class Meta:
        model = DigitalHumanLiveVideo
        fields = '__all__'


class ShortVideoCreateCheckClone:
    @staticmethod
    def execute(validated_data, request):
        user_code = request.user.user_code
        power_attorney_url = validated_data.get("power_attorney_url")
        live_video_url = validated_data.get("live_video_url")
        if not all([power_attorney_url, live_video_url]):
            raise CstException(RET.DATE_ERROR)
        a_obj = DigitalHumanActivateNumber.objects.filter(create_by=user_code, activate_status=1, activate_type_id=1).first()
        if not a_obj:
            raise CstException(RET.NO_NUMBER, "无可用次数， 请先兑换卡密")
        live_code = set_flow()
        validated_data["live_code"] = live_code
        validated_data["live_video_code"] = "dhc" + live_code + ".mp4"
        return a_obj


class ShortVideoDigitalHumanCloneSerializer(serializers.ModelSerializer):
    """
    短视频平台
    """
    create_cst = ShortVideoCreateCheckClone()

    def create(self, validated_data):
        request = self.context.get('request', None)
        a_obj = self.create_cst.execute(validated_data, request)
        validated_data.pop('is_delete', None)

        if request:
            try:
                validated_data['create_by'] = request.user.user_code
            except Exception as e:
                pass
        validated_data["make_status"] = 0
        with transaction.atomic():
            obj = super().create(validated_data)
            a_obj.activate_status = 2
            a_obj.save()
            DigitalHumanActivateConsumeHistory.objects.create(
                create_by=request.user.user_code,
                activate_type_id=2,
                usage_number=1
            )
        return obj

    class Meta:
        model = DigitalHumanLiveVideo
        fields = '__all__'


class CreateCheckProject:

    @staticmethod
    def execute(validated_data):
        return validated_data


class DigitalHumanProjectSerializer(BaseModelSerializer):
    """

    """
    create_cst = CreateCheckProject()

    class Meta:
        model = DigitalHumanProject
        fields = '__all__'


class CreateCheckVoice(object):
    @staticmethod
    def execute(validated_data):
        voice_name = validated_data.get("voice_name")
        gender = validated_data.get("gender")
        if gender not in ["female", "male"]:
            raise CstException(RET.DATE_ERROR, "性别选择错误")
        if DigitalHumanCustomizedVoice.objects.filter(voice_name=voice_name).exists():
            raise CstException(RET.DATE_ERROR, "该名称已被使用，请换个名称重试")
        voice_code = set_flow()
        validated_data["voice_code"] = voice_code
        return validated_data


class CustomizedVoiceSerializer(BaseModelSerializer):
    """

    """
    create_cst = CreateCheckVoice()

    class Meta:
        model = DigitalHumanCustomizedVoice
        fields = '__all__'