#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
"""
全局异常捕获
"""

import traceback

from rest_framework.views import exception_handler as drf_exception_handler
from django.db import DatabaseError
from redis.exceptions import RedisError
from django.conf import settings
from language.language_pack import RET
from utils.cst_class import CstResponse, CstException, ValidationError
import logging
logger = logging.getLogger(__name__)


def exception_handler(exc, context):
    """
    自定义异常处理
    :param exc: 异常
    :param context: 异常上下文
    :return: Response响应对象
    """
    response = drf_exception_handler(exc, context)

    if response is None:
        errmsg = None
        if settings.DEBUG:
            errmsg = str(exc)
        if isinstance(exc, DatabaseError) or isinstance(exc, RedisError):
            # 数据库异常
            logger.error(traceback.format_exc())
            response = CstResponse(RET.DB_ERR, errmsg)
        elif isinstance(exc, CstException):
            response = CstResponse(exc.code, exc.message, data=exc.data, status=exc.status)
        elif isinstance(exc, ValidationError):
            response = CstResponse(exc.code, exc.message)
        else:
            logger.error(traceback.format_exc())
            response = CstResponse(RET.SERVER_ERROR, errmsg)
    # if response and response.status_code == 400:
    #     logger.error(str(exc.detail))
    #     response = CstResponse(RET.DATAERR, exc.detail)
    #
    # if response and response.status_code != 200:
    #     logger.error(str(exc.detail))
    #     response = CstResponse(RET.DBERR, exc.detail)

    return response
