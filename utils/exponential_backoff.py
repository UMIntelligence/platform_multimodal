#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import asyncio
import logging
import random
import time
import uuid
from functools import wraps

import anthropic
import openai
import requests
from asgiref.sync import sync_to_async
from django_redis import get_redis_connection
from rest_framework import status

from language.language_pack import RET
from utils import constants
from utils.cst_class import CstException

logger = logging.getLogger(__name__)
time_out = 40

response = requests.get('https://api.ipify.org')
l_ip = response.text


def async_retry_with_exponential_backoff(
        func,
        initial_delay: float = 1,
        exponential_base: float = 2,
        jitter: bool = True,
        max_retries: int = 4,
        status=400,
        errors: tuple = (anthropic.RateLimitError,),
):
    """异步限流重试"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Initialize variables
        num_retries = 0
        delay = initial_delay

        # 循环，直到成功响应或达到max_retrys或引发异常
        while True:
            try:
                return await func(*args, **kwargs)
            # Retry on specific errors
            except errors as e:
                error = e.body.get("error")
                err_type = error.get("type")
                message = error.get("message")
                if err_type in ["rate_limit_error"]:
                    num_retries += 1

                    # Check if max retries has been reached
                    if num_retries > max_retries:
                        raise CstException(RET.TP_ERR, message, status=status)

                    # Increment the delay
                    delay += exponential_base * (1 + jitter * random.random())
                    # Sleep for the delay
                    await asyncio.sleep(delay)

                else:
                    raise CstException(RET.TP_ERR, message, status=status)

            # Raise exceptions for any errors not specified
            except anthropic.APIStatusError as e:
                message = e.message
                if e.status_code == 400 and e.body.get("error").get("type") == 'invalid_request_error':
                    message = "关联上下文，必须选中关联的一问一答"
                raise CstException(RET.TP_ERR, message, status=status)
            except anthropic.APIError as e:
                raise CstException(RET.TP_ERR, e.message, status=status)
    return wrapper


def async_retry_with_exponential_backoff_openai(
        func,
        initial_delay: float = 1,
        exponential_base: float = 2,
        jitter: bool = True,
        max_retries: int = 4,
        errors: tuple = (openai.PermissionDeniedError, openai.AuthenticationError),
):
    """异步限流重试"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Initialize variables
        num_retries = 0
        delay = initial_delay

        # 循环，直到成功响应或达到max_retrys或引发异常
        while True:
            try:
                return await func(*args, **kwargs)
            # Retry on specific errors
            except errors as e:
                err_type = e.response.json().get("error").get("code")
                if err_type is None:
                    raise CstException(RET.MAX_C_ERR, e.message, status=500)
                # print(e.error)
                # Increment retries
                if err_type in ["requests", "tokens", "server_error"]:
                    num_retries += 1

                    # Check if max retries has been reached
                    if num_retries > max_retries:
                        raise CstException(RET.TP_ERR, str(e.error), status=e.http_status)

                    # Increment the delay
                    delay += exponential_base * (1 + jitter * random.random())
                    logger.info(delay)
                    # Sleep for the delay
                    await asyncio.sleep(delay)
                elif err_type in ["insufficient_user_quota", "invalid_request_error", "billing_not_active"]:      # key余额不足或无效key需要更换key
                    obj = args[0]
                    chat_type = obj.chat_type
                    client_id = str(uuid.uuid1())
                    if chat_type in constants.GPT35:
                        lock_key = f"35key_{l_ip}_insufficient_quota"
                    elif chat_type in constants.GPT40:
                        lock_key = f"40key_{l_ip}_insufficient_quota"
                    else:
                        lock_key = f"dell_key_{l_ip}_insufficient_quota"
                    redis_conn = await sync_to_async(get_redis_connection)("default")
                    is_set = await sync_to_async(redis_conn.set)(lock_key, client_id, ex=time_out, nx=True)
                    if not is_set:
                        time.sleep(delay)
                        continue

                    await sync_to_async(obj.change_key)(redis_conn)
                    await sync_to_async(obj.set_api_key)()
                else:
                    raise CstException(RET.TP_ERR, str(e.error), status=e.http_status)

            # Raise exceptions for any errors not specified
            except openai.APIError as e:
                logger.error(f"{e.message}-----{e}")
                raise CstException(RET.TP_ERR, str(e.message), status=400)

            except Exception as e:
                logger.error(f"{e}-----")
                raise CstException(RET.TP_ERR, str(e), status=status.HTTP_303_SEE_OTHER)
    return wrapper


def image_exponential_backoff_openai(
        func,
        initial_delay: float = 1,
        exponential_base: float = 2,
        jitter: bool = True,
        max_retries: int = 4,
        errors: tuple = (openai.RateLimitError, openai.AuthenticationError),
):
    """限流重试"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Initialize variables
        num_retries = 0
        delay = initial_delay

        # 循环，直到成功响应或达到max_retrys或引发异常
        while True:
            try:
                return func(*args, **kwargs)
            except errors as e:
                err_type = e.type
                if err_type is None:
                    raise CstException(RET.MAX_C_ERR, e.message)
                if err_type in ["requests", "tokens", "server_error"]:
                    num_retries += 1

                    # Check if max retries has been reached
                    if num_retries > max_retries:
                        raise CstException(RET.TP_ERR, str(e.error))

                    # Increment the delay
                    delay += exponential_base * (1 + jitter * random.random())
                    logger.info(delay)
                    # Sleep for the delay
                    time.sleep(delay)
                elif err_type in ["insufficient_quota", "invalid_request_error", "billing_not_active"]:      # key余额不足或无效key需要更换key
                    raise CstException(RET.KEY_ERR)
                else:
                    raise CstException(RET.TP_ERR, str(e.error))

            # Raise exceptions for any errors not specified
            except openai.APIError as e:
                logger.error(f"{e.message}-----{e}")
                raise CstException(RET.TP_ERR, str(e.message))

            except Exception as e:
                logger.error(f"{e}-----")
                raise CstException(RET.TP_ERR, str(e))
    return wrapper
