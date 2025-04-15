#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import logging

from django.db import connections

logger = logging.getLogger('django')
# ref: django.db.close_old_connections


def close_old_connections():
    for conn in connections.all():
        conn.close_if_unusable_or_obsolete()


def handle_db_connections(func):
    def func_wrapper(*args,**kwargs):
        close_old_connections()
        logger.info('处理连接')
        result = func(*args,**kwargs)
        close_old_connections()

        return result

    return func_wrapper
