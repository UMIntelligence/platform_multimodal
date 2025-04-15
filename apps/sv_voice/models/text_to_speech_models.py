#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import models

from utils.base_models import BaseModel


class VtTextToSpeechEngine(BaseModel):

    engine_code = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="引擎唯一编号")
    engine_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="引擎名称")
    class_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="调用函数名称")
    model = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="")
    scene_type = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="场景类型，")

    class Meta:
        managed = False
        db_table = 'vt_text_to_speech_engine'
        verbose_name = '文本转语音引擎表'
        verbose_name_plural = verbose_name


class VtTextToSpeechVoice(BaseModel):

    # engine_code = models.ForeignKey(VtTextToSpeechEngine, on_delete=models.CASCADE, related_name='engine_voices', verbose_name="引擎", to_field='engine_code')
    engine_code = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="引擎唯一编号")
    voice_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="音色编号")
    voice = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="音色")
    voice_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="音色名称")
    voice_logo = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="音色logo")
    speech_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="speech_url")
    language = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="语言")
    desc = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="语言")
    voice_type = models.IntegerField(blank=True, null=True, default=1, help_text="类型，1通用，2个人训练")
    v_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：正常，2:过期")
    gender = models.IntegerField(blank=True, null=True, default=1, help_text="性别1：男，2:女，0：未知")

    class Meta:
        managed = False
        db_table = 'vt_text_to_speech_voice'
        verbose_name = '文本转语音音色表'
        verbose_name_plural = verbose_name


class VtTextToSpeechHistory(BaseModel):

    h_code = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="唯一编号")
    engine_code = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="引擎唯一编号")
    voice_code = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="音色编号")
    title = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="")
    content = models.TextField(blank=True, null=True, default="", verbose_name="内容")
    speech_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="声音url")
    language = models.CharField(max_length=64, blank=True, null=True, default="zh", verbose_name="合成文本语言")
    task_id = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="task_id")

    h_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：生成中，2:成功,3:生成失败")
    speech_rate = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, default=0.00, help_text="语速")
    pitch_rate = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, default=0.00, help_text="语调")

    class Meta:
        managed = False
        db_table = 'vt_text_to_speech_history'
        verbose_name = '文本转语音音色表'
        verbose_name_plural = verbose_name
