#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import models

from utils.base_models import BaseModel


class CCChatSquare(BaseModel):
    S_STATUS = (
        (1, "待审核"),
        (2, "已审核"),
        (3, "已驳回"),
    )

    session_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="会话唯一编号")
    chat_group_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="冗余")
    module_id = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="")
    question_id = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="")
    question_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="")

    s_status = models.IntegerField(blank=True, null=True, default=1, choices=S_STATUS, verbose_name="类型")

    class Meta:
        managed = False
        db_table = 'cc_chat_square'
        verbose_name = '问答广场主表'
        verbose_name_plural = verbose_name


class CCChatPrompt(models.Model):

    question_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="唯一编号")
    question_data = models.JSONField(verbose_name="提示词json")

    class Meta:
        managed = False
        db_table = 'cc_chat_prompt'
        verbose_name = '问答广场提示词表'
        verbose_name_plural = verbose_name


class CCChatMessages(models.Model):

    session_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="会话唯一编号")
    session_data = models.JSONField(verbose_name="消息json")

    class Meta:
        managed = False
        db_table = 'cc_chat_messages'
        verbose_name = '问答广场提示词表'
        verbose_name_plural = verbose_name