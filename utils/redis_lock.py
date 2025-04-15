#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import abc
import copy
import functools
import hashlib
import json
import uuid
from contextlib import contextmanager, asynccontextmanager

from asgiref.sync import sync_to_async
from django_redis import get_redis_connection

from language.language_pack import RET
from utils.cst_class import CstException
from utils.ip_utils import get_client_ip


class LockKeyBase(abc.ABC):

    @abc.abstractmethod
    def get_key(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def delete_key(self, *args, **kwargs):
        pass


class ViewKey(LockKeyBase):

    def __init__(self, view_instance, request):
        self.request = request
        self.view_instance = view_instance

    def get_key(self, *args, **kwargs):

        return self._get_key(self.view_instance, self.request.method, self.request, *args, **kwargs)

    def _get_key(self, view_instance, view_method, request, *args, **kwargs):
        try:
            data = view_instance.lock_custom(view_instance, request, *args, **kwargs)  # 自定义参数使用锁，在原类中实现lock_custom方法
        except AttributeError as e:
            data = copy.deepcopy(request.data)

        _kwargs = {
            'view_instance': view_instance.__class__.__name__,
            'view_method': view_method,
            'request': data,
            'args': args,
            'kwargs': kwargs,
        }
        return self.prepare_key(_kwargs)

    @staticmethod
    def prepare_key(key_dict):
        return hashlib.md5(json.dumps(key_dict, sort_keys=True).encode('utf-8')).hexdigest()

    def delete_key(self, redis_conn, key, client_id):
        goods_id_bit = redis_conn.get(key)
        if goods_id_bit:
            client_id_str = goods_id_bit.decode("utf-8")
            if client_id == client_id_str:
                redis_conn.delete(key)


class ViewIpKey(LockKeyBase):

    def __init__(self, view_instance, request):
        self.request = request
        self.view_instance = view_instance

    def get_key(self, *args, **kwargs):

        return self._get_key(self.view_instance, self.request.method, self.request, *args, **kwargs)

    def _get_key(self, view_instance, view_method, request, *args, **kwargs):

        _kwargs = {
            'view_instance': view_instance.__class__.__name__,
            'view_method': view_method,
            'request': request.user.user_code,
            'args': args,
            'kwargs': kwargs,
        }
        return self.prepare_key(_kwargs)

    @staticmethod
    def prepare_key(key_dict):
        return hashlib.md5(json.dumps(key_dict, sort_keys=True).encode('utf-8')).hexdigest()

    def delete_key(self, redis_conn, key, client_id):
        pass
        # goods_id_bit = redis_conn.get(key)
        # if goods_id_bit:
        #     client_id_str = goods_id_bit.decode("utf-8")
        #     if client_id == client_id_str:
        #         redis_conn.delete(key)


@contextmanager
def redis_locks(view_instance, request, key_class, db_name, time_out, status):
    """
    redis锁限制重复提交，未开续命线程
    :param view_instance:
    :param request:
    :param key_class:
    :param db_name:
    :param time_out:
    :return:
    """

    client_id = str(uuid.uuid1())
    key_class = key_class(view_instance, request)
    key = key_class.get_key()
    redis_conn = get_redis_connection(db_name)
    is_set = redis_conn.set(key, client_id, ex=time_out, nx=True)

    if not is_set:
        raise CstException(RET.FREQUENTLY, status=status)
    try:
        yield redis_conn
    finally:
        key_class.delete_key(redis_conn, key, client_id)


class LockRequest(object):
    def __init__(self, key_class=ViewKey, time_out=30, db_name='default', status=200, *args, **kwargs):
        """
        key_prefix (class)): key名前缀
        time_out (int, optional): 过期时间
        db_name (str, optional): [description]. redis数据库名称
        """
        self.key_class = key_class
        self.time_out = time_out
        self.db_name = db_name
        self.status = status

    def __call__(self, func):
        """
        Args:
            func: 视图方法
        Returns:
            inner: 装饰器
        """

        @functools.wraps(func)
        def inner(view_instance, request, *args, **kwargs):
            """
            view_instance: 视图实例
            request: Request请求
            pk: 主键
            """
            with redis_locks(self, request, self.key_class, self.db_name, self.time_out, self.status) as rc:
                return func(view_instance, request, *args, **kwargs)

        return inner


class AsyncViewKey(LockKeyBase):
    def __init__(self, view_instance, request):
        self.request = request
        self.view_instance = view_instance

    def get_key(self, *args, **kwargs):
        return self._get_key(self.view_instance, self.request.method, self.request, *args, **kwargs)

    def _get_key(self, view_instance, view_method, request, *args, **kwargs):
        try:
            data = view_instance.lock_custom(view_instance, request, *args, **kwargs)
        except AttributeError as e:
            data = copy.deepcopy(request.data)

        _kwargs = {
            'view_instance': view_instance.__class__.__name__,
            'view_method': view_method,
            'request': data,
            'args': args,
            'kwargs': kwargs,
        }
        return self.prepare_key(_kwargs)

    @staticmethod
    def prepare_key(key_dict):
        return hashlib.md5(json.dumps(key_dict, sort_keys=True).encode('utf-8')).hexdigest()

    async def delete_key(self, redis_conn, key, client_id):
        goods_id_bit = await sync_to_async(redis_conn.get)(key)
        if goods_id_bit:
            client_id_str = goods_id_bit.decode("utf-8")
            if client_id == client_id_str:
                await sync_to_async(redis_conn.delete)(key)


@asynccontextmanager
async def async_redis_locks(view_instance, request, key_class, db_name, time_out, status):
    client_id = str(uuid.uuid1())
    key_class = key_class(view_instance, request)
    key = key_class.get_key()
    redis_conn = await sync_to_async(get_redis_connection)(db_name)
    is_set = await sync_to_async(redis_conn.set)(key, client_id, ex=time_out, nx=True)

    if not is_set:
        raise CstException(RET.FREQUENTLY, status=status)

    try:
        yield redis_conn
    finally:
        await key_class.delete_key(redis_conn, key, client_id)


class AsyncLockRequest(object):
    def __init__(self, key_class=AsyncViewKey, time_out=30, db_name='default', status=200, *args, **kwargs):
        """
        key_prefix (class)): key名前缀
        time_out (int, optional): 过期时间
        db_name (str, optional): [description]. redis数据库名称
        """
        self.key_class = key_class
        self.time_out = time_out
        self.db_name = db_name
        self.status = status

    def __call__(self, func):
        """
        Args:
            func: 视图方法
        Returns:
            inner: 装饰器
        """

        @functools.wraps(func)
        async def inner(view_instance, request, *args, **kwargs):
            """
            view_instance: 视图实例
            request: Request请求
            pk: 主键
            """
            async with async_redis_locks(view_instance, request, self.key_class, self.db_name, self.time_out, self.status) as rc:
                return await func(view_instance, request, *args, **kwargs)

        return inner
