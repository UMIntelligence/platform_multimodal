#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import models

from utils.base_models import BaseModel


class CgChatRole(BaseModel):
    CHAT_TYPE = (
        (0, "gpt3.5"),
        (1, "gpt4.0"),
        (2, "dell2绘图"),
        (3, "百度绘图"),
        (4, "文心一言"),
        (5, "科大讯飞"),
        (6, "mj绘画"),
        (7, "ClaudeChat"),
        (8, "ChatGLM"),
        (9, "sd"),
        (10, "QwEn"),
        (11, "SenseNova"),
    )

    role_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="角色编号")
    role_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="角色名称")
    role_logo = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="角色log")
    chat_type = models.IntegerField(blank=True, null=True, default=0, choices=CHAT_TYPE, verbose_name="绑定的模型类型")
    model = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="绑定的模型")
    covert_content = models.CharField(max_length=1024, blank=True, null=True, default="", verbose_name="提示词")
    role_type = models.IntegerField(blank=True, null=True, default=2, verbose_name="类型，1，通用，2：私人")

    class Meta:
        managed = False
        db_table = 'cg_chat_role'
        verbose_name = '对话角色表'
        verbose_name_plural = verbose_name


class CgGroupChatRole(BaseModel):
    group_role_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="群聊角色编号")
    role_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="角色编号")
    session_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="")
    sort_no = models.CharField(max_length=20, blank=True, null=True, default="1", verbose_name="排序号")

    class Meta:
        managed = False
        db_table = 'cg_group_chat_role'
        verbose_name = '对话群聊角色表'
        verbose_name_plural = verbose_name


class CgGroupChat(BaseModel):

    session_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="会话唯一编号")
    title = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="标题")
    subject = models.CharField(max_length=1024, blank=True, null=True, default="", verbose_name="主题")
    total_integral = models.IntegerField(blank=True, null=True, default=0, verbose_name="全部可用算力")
    use_integral = models.IntegerField(blank=True, null=True, default=0, verbose_name="可用算力")
    source = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="来源")

    class Meta:
        managed = False
        db_table = 'cg_group_chat'
        verbose_name = '对话群聊表'
        verbose_name_plural = verbose_name


class CgGroupChatDtl(BaseModel):
    IS_LIKES = (
        (0, "不点"),
        (1, "点赞"),
        (2, "点踩"),
    )

    session_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="会话唯一编号")
    msg_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="dtl唯一编号")
    finish_reason = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="结束原因:length")
    group_role_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="群聊角色编号")
    chat_type = models.IntegerField(blank=True, null=True, default="0", verbose_name="对话类型，当role_code为空时需要存")
    model = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="标题")

    role = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="角色:user,system,assistant")
    content = models.TextField(blank=True, null=True, default="", verbose_name="内容")
    covert_content = models.TextField(blank=True, null=True, default="", verbose_name="隐性内容")

    total_tokens = models.IntegerField(blank=True, null=True, default=0, verbose_name="聊天总长度")
    completion_tokens = models.IntegerField(blank=True, null=True, default=0, verbose_name="返回长度")
    prompt_tokens = models.IntegerField(blank=True, null=True, default=0, verbose_name="问题长度")
    integral = models.IntegerField(blank=True, null=True, default=0, verbose_name="积分")
    is_likes = models.IntegerField(blank=True, null=True, default=0, choices=IS_LIKES, verbose_name="点赞行为")
    is_mod = models.IntegerField(blank=True, null=True, default=0, verbose_name="是否违规，0否，1是")

    class Meta:
        managed = False
        db_table = 'cg_group_chat_dtl'
        verbose_name = '对话群聊表'
        verbose_name_plural = verbose_name
