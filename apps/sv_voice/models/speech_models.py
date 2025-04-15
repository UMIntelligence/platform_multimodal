#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import models

from utils.base_models import BaseModel


class SpeechRecognitionHistory(BaseModel):

    speech_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="记录编号")
    biz_duration = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="识别时长")
    title = models.CharField(max_length=256, blank=True, null=True, default="记录", verbose_name="title")
    audio_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="原音频地址")
    file_type = models.IntegerField(blank=True, null=True, default=2, help_text="文件类型1:图片，2：音频，3：视频")
    file_name = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="文件名称")
    speech_text = models.TextField(blank=True, null=True, default="", verbose_name="内容")

    r_status = models.IntegerField(blank=True, null=True, default=1, verbose_name="状态1:录音中，2完成")
    r_type = models.IntegerField(blank=True, null=True, default=1, verbose_name="类型，1：实时语音，2：音视频撰写")

    class Meta:
        managed = False
        db_table = 'vs_speech_recognition_history'
        verbose_name = '语音识别历史表'
        verbose_name_plural = verbose_name
