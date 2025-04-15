#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from collections import OrderedDict

from rest_framework import serializers
from rest_framework.fields import SkipField, DateTimeField
from rest_framework.relations import PKOnlyObject


class CreateCheck:

    @staticmethod
    def execute(validated_data):
        return dict()


class UpdateCheck:

    @staticmethod
    def execute(validated_data, instance=None):
        return dict()


class BaseModelSerializer(serializers.ModelSerializer):
    """

    """

    create_cst = CreateCheck()          # 创建校验类
    update_cst = UpdateCheck()          # 修改校验类

    def create(self, validated_data):
        _ = self.create_cst.execute(validated_data)
        validated_data.pop('is_delete', None)

        request = self.context.get('request', None)
        if request:
            try:
                validated_data['create_by'] = request.user.user_code
            except Exception as e:
                pass

        return super().create(validated_data)

    def update(self, instance, validated_data):
        _ = self.update_cst.execute(validated_data, instance)
        validated_data.pop('is_delete', None)

        # request = self.context.get('request', None)
        # if request:
        #     validated_data['modify_by'] = request.user.user_code

        return super().update(instance, validated_data)

    def to_representation(self, instance):
        """
        Object instance -> Dict of primitive datatypes.
        """
        ret = OrderedDict()
        fields = self._readable_fields

        for field in fields:
            try:
                attribute = field.get_attribute(instance)
            except SkipField:
                continue

            # We skip `to_representation` for `None` values so that fields do
            # not have to explicitly deal with that case.
            #
            # For related fields with `use_pk_only_optimization` we need to
            # resolve the pk value.
            check_for_none = attribute.pk if isinstance(attribute, PKOnlyObject) else attribute
            if check_for_none is None:
                ret[field.field_name] = None
            else:
                if isinstance(field, DateTimeField):
                    field.format = r'%Y-%m-%d %H:%M:%S'
                ret[field.field_name] = field.to_representation(attribute)

        return ret
