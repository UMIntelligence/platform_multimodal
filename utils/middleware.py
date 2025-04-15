#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import logging
import json
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class LogMiddleware(MiddlewareMixin):

    def process_request(self, request):
        if str(request.method).upper() == "GET":
            return
        try:
            msg = '{}-{}\n GET {}\n POST {}'.format(request.path, request.method, json.dumps(request.GET), request.body.decode('utf8'))
            logger.info(msg)
        except Exception as e:
            pass
