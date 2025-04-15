#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
"""
日志   工具类

"""
import logging

from rest_framework.response import Response
# from rest_framework_extensions.key_constructor.constructors import DefaultKeyConstructor

# from rest_framework_extensions.key_constructor.constructors import DefaultKeyConstructor
from language.language_pack import Language

logger = logging.getLogger(__name__)


class CstResponse(Response):

    def __init__(self, code, message=None, data=None, **kwargs):
        """
        自定义返回数据
        :param data: 返回数据
        :param code: 返回状态码
        :param message: 返回消息
        """
        if not message:
            message = Language.get(code)

        dic_data = dict(
            code=int(code),
            msg=message
        )
        if data:
            dic_data['data'] = data
        else:
            dic_data['data'] = None
        super(CstResponse, self).__init__(dic_data, **kwargs)


class CstException(Exception):
    """
    业务异常类
    """

    def __init__(self, code, message=None, data=None, status=200):
        self.code = code
        self.message = message
        self.status = status
        self.data = data
        super(CstException, self).__init__()


class ImageException(Exception):
    """
    业务异常类
    """

    def __init__(self, code, message=None, status=200):
        self.code = code
        self.message = message
        self.status = status
        super(ImageException, self).__init__()


class ValidationError(Exception):
    """
    业务异常类
    """

    def __init__(self, code, message=None):
        self.code = code
        self.message = message
        super(ValidationError, self).__init__(message)


# class CstKeyConstructor(DefaultKeyConstructor):
#
#     """
#     _kwargs = {
#             'view_instance': view_instance,
#             'view_method': view_method,
#             'request': request,
#             'args': args,
#             'kwargs': kwargs,
#         }
#     """
#
#     def get_data_from_bits(self, **kwargs):
#         result_dict = {}
#         for bit_name, bit_instance in self.bits.items():
#             if bit_name in self.params:
#                 params = self.params[bit_name]
#             else:
#                 try:
#                     params = bit_instance.params
#                 except AttributeError:
#                     params = None
#             result_dict[bit_name] = bit_instance.get_data(
#                 params=params, **kwargs)
#         for key, value in kwargs.items():
#             if key == "request":
#                 key_list = value.query_params.keys()
#                 for i in key_list:
#                     result_dict[i] = value.query_params[i]
#         return result_dict
