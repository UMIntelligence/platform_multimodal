#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from language.language_pack import RET
from apps.se_enterprise.models.enterprise_models import CeEnterpriseMember, CeEnterpriseDigitalClerk
from sv_voice.serializers.base_serializers import BaseModelSerializer
from utils.cst_class import CstException
from utils.generate_number import set_flow


class CreateCheckMember:
    @staticmethod
    def execute(validated_data):
        company_code = validated_data.get("company_code")
        user_code = validated_data.get("user_code")
        invite_user_code = validated_data.get("invite_user_code")
        if not all([company_code, user_code, invite_user_code]):
            raise CstException(RET.DATE_ERROR)
        if CeEnterpriseMember.objects.filter(company_code=company_code, user_code=user_code).exists():
            raise CstException(RET.DATE_ERROR, "已经被邀请过了")
        member_code = set_flow()
        validated_data["member_code"] = member_code
        return validated_data


class EnterpriseMemberSerializer(BaseModelSerializer):
    create_cst = CreateCheckMember()

    class Meta:
        model = CeEnterpriseMember
        fields = '__all__'


class CreateCheckDigitalClerk:

    @staticmethod
    def execute(validated_data):
        company_code = validated_data.get("company_code")
        knowledge_code = validated_data.get("knowledge_code")
        if not all([company_code, knowledge_code]):
            raise CstException(RET.DATE_ERROR)
        if CeEnterpriseDigitalClerk.objects.filter(company_code=company_code, knowledge_code=knowledge_code, is_delete=0).exists():
            raise CstException(RET.DATE_ERROR, "该知识库已创建过，请不要重复创建数字员工")
        clerk_code = set_flow()
        validated_data["clerk_code"] = clerk_code
        return validated_data


class UpdateCheckDigitalClerk:
    @staticmethod
    def execute(validated_data, instance=None):
        validated_data.pop("clerk_code", "")
        validated_data.pop("company_code", "")
        validated_data.pop("knowledge_code", "")
        return validated_data


class EnterpriseDigitalClerkSerializer(BaseModelSerializer):
    create_cst = CreateCheckDigitalClerk()  # 创建校验类
    update_cst = UpdateCheckDigitalClerk()

    class Meta:
        model = CeEnterpriseDigitalClerk
        fields = '__all__'
