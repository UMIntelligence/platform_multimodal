#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """为模型类补充字段"""
    create_by = models.CharField(max_length=64, blank=True, null=True, default="", help_text="创建人唯一编号")
    create_time = models.DateTimeField(blank=True, null=True, default=timezone.now, verbose_name="创建时间")
    modify_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    is_delete = models.IntegerField(blank=True, null=True, default=0, help_text="是否删除。1：删除，0：否")

    objects = models.Manager()

    class Meta:
        abstract = True
