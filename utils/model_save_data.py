#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI


def get_model_field_name(model, exclude=None):
    """

    :param model:
    :param exclude:
    :return:
    """
    exclude = exclude or []
    consistent = model
    columns = [field.name for field in consistent._meta.fields if field.name not in exclude]
    return columns


class ModelSaveData(object):
    """
    orm模型字段获取
    """

    @staticmethod
    def get_request_save_data(data, model, exclude=None):
        """

        :param data:
        :param model:
        :param exclude:
        :return:
        """
        columns = get_model_field_name(model, exclude=exclude)
        if isinstance(data, dict):
            save_data = {}
            for key in data.keys():
                if key in columns:
                    save_data[key] = data.get(key)
        else:
            save_data = []
            for value in data:
                model_dict = {}
                for i in list(value.keys()):
                    if i in columns:
                        model_dict[i] = value[i]
                save_data.append(model_dict)
        return save_data


