#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import models

from utils.base_models import BaseModel


class CeEnterpriseInfo(BaseModel):

    company_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="公司编号")
    company_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="公司名称")
    company_abbreviation = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="公司简称")
    position = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="职位")
    industry_code = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="行业编号")
    registered_address = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="注册地址")
    company_desc = models.CharField(max_length=512, blank=True, null=True, default="", verbose_name="公司描述")
    company_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="公司网址")
    ipc_code = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="ipc备案号")
    icon_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="icon_url")
    company_mobile = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="公司电话")
    company_mailbox = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="公司邮箱")
    company_address = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="公司地址")
    status = models.IntegerField(blank=True, null=True, default=1, verbose_name="状态，1：保存，2提交")

    class Meta:
        managed = False
        db_table = 'ce_enterprise_info'
        verbose_name = '企业信息表'
        verbose_name_plural = verbose_name


class CeEnterpriseProjectInfo(BaseModel):

    company_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="公司编号")
    project_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="项目编号")
    category_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="类目名称")
    project_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="项目名称")
    brief_introduction = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="简介")

    class Meta:
        managed = False
        db_table = 'ce_enterprise_project_info'
        verbose_name = '企业项目信息表'
        verbose_name_plural = verbose_name


class CeEnterpriseInformationInfo(BaseModel):

    company_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="公司编号")
    information_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="资讯编号")
    label_code = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="资讯信息编号")
    information_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="资讯名称")
    content_desc = models.CharField(max_length=512, blank=True, null=True, default="", verbose_name="内容描述")

    class Meta:
        managed = False
        db_table = 'ce_enterprise_information_info'
        verbose_name = '企业资讯信息表'
        verbose_name_plural = verbose_name


class CeEnterpriseKnowledgeBase(BaseModel):

    company_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="公司编号")
    knowledge_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="知识库编号")
    category_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="资讯信息名称")
    category = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="资讯信息编号")
    content_desc = models.CharField(max_length=512, blank=True, null=True, default="", verbose_name="内容描述")
    purpose = models.CharField(max_length=512, blank=True, null=True, default="", verbose_name="用途")
    title = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="标题")

    class Meta:
        managed = False
        db_table = 'ce_enterprise_knowledge_base'
        verbose_name = '企业知识库信息表'
        verbose_name_plural = verbose_name


class CeEnterpriseLabel(BaseModel):

    label_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="分类编号")
    label = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="分类名")
    label_type = models.IntegerField(blank=True, null=True, default=1, verbose_name="类型1行业，2资讯，3：分类")

    class Meta:
        managed = False
        db_table = 'ce_enterprise_label'
        verbose_name = '企业标签选项表'
        verbose_name_plural = verbose_name


class CeEnterpriseFiles(BaseModel):
    FILE_CATEGORY = (
        (1, "企业文件"),
        (2, "项目文件"),
        (3, "资讯文件"),
        (4, "知识库文件"),
    )

    code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="关联编号")
    file_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="文件地址")
    file_name = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="文件名称")
    group_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="组编号")
    file_category = models.IntegerField(blank=True, null=True, default=0, choices=FILE_CATEGORY, verbose_name="文件分类")

    class Meta:
        managed = False
        db_table = 'ce_enterprise_files'
        verbose_name = '企业文件表'
        verbose_name_plural = verbose_name


class CeEnterpriseMember(BaseModel):

    member_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="成员编号")
    company_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="公司编号")
    user_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="被邀请用户编号")
    invite_user_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="邀请用户编号")
    m_status = models.IntegerField(blank=True, null=True, default=1, verbose_name="状态，1待审核，2已审核")

    class Meta:
        managed = False
        db_table = 'ce_enterprise_member'
        verbose_name = '企业成员表'
        verbose_name_plural = verbose_name


class CeEnterpriseDigitalClerk(BaseModel):

    clerk_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="数字员工编号")
    company_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="公司编号")
    knowledge_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="知识库编号")
    clerk_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="数字员工名称")
    icon_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="图标")
    welcome_msg = models.CharField(max_length=512, blank=True, null=True, default="", verbose_name="欢迎语")
    d_status = models.IntegerField(blank=True, null=True, default=1, verbose_name="状态，1训练中，2正常")

    class Meta:
        managed = False
        db_table = 'ce_enterprise_digital_clerk'
        verbose_name = '企业数字员工表'
        verbose_name_plural = verbose_name
