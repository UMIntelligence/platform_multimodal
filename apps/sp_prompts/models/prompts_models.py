#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import models

from utils.base_models import BaseModel


class CMModelPromptsType(BaseModel):

    type_name = models.CharField(max_length=128, blank=True, null=True, default="", verbose_name="类型名称")
    type_desc = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="类型描述")
    is_weight = models.IntegerField(blank=True, null=True, default=0, help_text="权重0不推荐，1推荐")

    class Meta:
        managed = False
        db_table = 'cm_model_prompts_type'
        verbose_name = '模型指令分类表'
        verbose_name_plural = verbose_name


class CMModelPrompts(BaseModel):
    prompts_type = models.ForeignKey(CMModelPromptsType, models.DO_NOTHING, blank=True, null=True, default=-1, related_name="prompts_type")  # to_field='lineplanid',

    prompts_name = models.CharField(max_length=512, blank=True, null=True, default="", verbose_name="指令")
    prompts_desc = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="指令描述")
    prompts_title = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="指令标题")
    p_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：正常，2：禁用")
    uses_number = models.IntegerField(blank=True, null=True, default=0, help_text="使用次数")

    class Meta:
        managed = False
        db_table = 'cm_model_prompts'
        verbose_name = '模型指令分类表'
        verbose_name_plural = verbose_name
