#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json
import logging
import threading
import time
import traceback
from datetime import datetime

import pika
from django.conf import settings

logger = logging.getLogger('django')


class RabbitMqObj:

    def __init__(self):
        mq_config = settings.MQ["ty"]
        user = mq_config.get("USER")
        password = mq_config.get("PASSWORD")
        host = mq_config.get("HOST")
        port = mq_config.get("PORT")
        vhost = mq_config.get("vhost")
        credentials = pika.PlainCredentials(user, password)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, port=port, virtual_host=vhost, credentials=credentials))   # , heartbeat=120
        self.channel = self.connection.channel()
        self.queue_durable = True  # 管道持久化 True为开启 Fale为不持久化
        self.exchange_durable = True  # 交换机持久化 True为开启 Fale为不持久化
        self.auto_ack = False  # 应答模式 True为自动应答 Fale为手动确认
        self.properties = pika.BasicProperties(delivery_mode=2)  # delivery_mode = 2 声明消息在队列中持久化，delivery_mod = 1 消息非持久化

    def set_queue_durable(self, durable_bool: bool):
        # 管道持久化 True为开启Fale为不持久化
        self.queue_durable = durable_bool

    def set_exchange_durable(self, exchange_bool: bool):
        # 管道持久化 True为开启Fale为不持久化
        self.exchange_durable = exchange_bool

    def set_properties(self, num: int):
        # delivery_mode = 2 声明消息在队列中持久化，delivery_mod = 1 消息非持久化
        self.properties = pika.BasicProperties(delivery_mode=num)

    def ste_auto_ack(self, auto_ack_bool: bool):
        # 应答模式 True为自动应答 Fale为手动确认
        self.auto_ack = auto_ack_bool

    def set_delay(self, delay):
        # 死信队列
        arguments = dict()
        if delay:
            # 处理死信队列
            arguments['x-message-ttl'] = 1000 * 60 * 60  # 延迟时间 （毫秒）
            arguments['x-dead-letter-exchange'] = ""
            delay_exchange = delay.get("exchange")
            # delay_queue = delay.get("queue")
            delay_routing_key = delay.get("routing_key")
            timeout = delay.get("timeout")
            if delay_exchange:
                arguments['x-dead-letter-exchange'] = delay_exchange
            if delay_routing_key:
                arguments['x-dead-letter-routing-key'] = delay_routing_key
            # if delay_queue:
            #     arguments['x-dead-letter-queue'] = delay_queue
            if timeout:
                arguments['x-message-ttl'] = timeout
        return arguments

    def send_vail(self, *args, **kwargs):
        pass

    def bin_func(self, *args, **kwargs):
        pass

    def send_func(self, *args, **kwargs):
        pass


class RabbitMqConsumer(RabbitMqObj):
    # 生产者，消费者模式
    def __init__(self):
        super().__init__()

    def bin_vail(self, data):

        queue = data.get("queue")
        if not queue:
            raise Exception("生产消费者模式,必须申明queue名称")

        callback = data.get("callback")
        if not callback:
            raise Exception("必须填写回调方法")

    def send_vail(self, data):

        queue = data.get("queue")
        if not queue:
            raise Exception("生产消费者模式,必须申明queue名称")

        msg = data.get("msg")
        if not msg:
            raise Exception("msg")

    def bin_func(self, data):
        # 参数校验
        self.bin_vail(data)
        queue = data.get("queue")
        callback = data.get("callback")
        delay = data.get("delay")
        # 死信设置
        arguments = self.set_delay(delay)
        # 声明管道
        result = self.channel.queue_declare(queue=queue, durable=self.queue_durable, arguments=arguments)
        # 告诉rabbitmq，用callback来接收消息
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(result.method.queue, callback, auto_ack=self.auto_ack)
        # 开始接收信息，并进入阻塞状态，队列里有信息才会调用callback进行处理
        self.channel.start_consuming()

    def send_func(self, data):
        # 参数校验
        self.send_vail(data)
        queue = data.get("queue")
        msg = json.dumps(data.get("msg"))
        # 投入管道
        self.channel.basic_publish(exchange='', routing_key=queue, body=msg)
        self.connection.close()


class RabbitMqFanout(RabbitMqObj):
    # 订阅模式
    def __init__(self):
        super().__init__()

    def bin_vail(self, data):

        queue = data.get("queue")
        if not queue:
            raise Exception("订阅模式,必须申明queue名称")

        exchange = data.get("exchange")
        if not exchange:
            raise Exception("订阅模式,必须申明exchange名称")

        callback = data.get("callback")
        if not callback:
            raise Exception("必须填写回调方法")

    def send_vail(self, data):

        exchange = data.get("exchange")
        if not exchange:
            raise Exception("订阅模式,必须申明exchange名称")

        msg = data.get("msg")
        if not msg:
            raise Exception("msg")

    def bin_func(self, data):
        # 校验
        self.bin_vail(data)
        queue = data.get("queue")
        callback = data.get("callback")
        exchange = data.get("exchange")
        delay = data.get("delay")
        # 死信设置
        arguments = self.set_delay(delay)
        print(arguments)
        # 声明队列
        result = self.channel.queue_declare(queue=queue, durable=self.queue_durable, arguments=arguments)
        # 声明交换机
        self.channel.exchange_declare(exchange=exchange, durable=self.exchange_durable, exchange_type="fanout")
        # 交换机和管道绑定
        self.channel.queue_bind(exchange=exchange, queue=result.method.queue)
        # 管道和方法绑定
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(result.method.queue, callback, auto_ack=self.auto_ack)
        self.channel.start_consuming()

    def send_func(self, data):
        self.send_vail(data)
        exchange = data.get("exchange")
        msg = json.dumps(data.get("msg"))
        # 声明
        self.channel.exchange_declare(exchange=exchange, durable=self.exchange_durable, exchange_type="fanout")
        # 消息投掷到交换机
        self.channel.basic_publish(exchange=exchange, routing_key='', body=msg,
                                   properties=self.properties)
        self.connection.close()


class RabbitMqDirect(RabbitMqObj):
    # 主题模式
    def __init__(self):
        super().__init__()

    def bin_vail(self, data):

        queue = data.get("queue")
        if not queue:
            raise Exception("主题模式,必须申明queue名称")

        exchange = data.get("exchange")
        if not exchange:
            raise Exception("主题模式,必须申明exchange名称")

        routing_key = data.get("routing_key")
        if not routing_key:
            raise Exception("主题模式,必须申明routing_key名称")

        callback = data.get("callback")
        if not callback:
            raise Exception("必须填写回调方法")

    def send_vail(self, data):

        exchange = data.get("exchange")
        if not exchange:
            raise Exception("主题模式,必须申明exchange名称")

        routing_key = data.get("routing_key")
        if not routing_key:
            raise Exception("主题模式,必须申明routing_key名称")

        msg = data.get("msg")
        if not msg:
            raise Exception("msg")

    def bin_func(self, data):
        # 校验
        self.bin_vail(data)
        queue = data.get("queue")
        callback = data.get("callback")
        exchange = data.get("exchange")
        routing_key = data.get("routing_key")
        type = data.get("type")
        delay = data.get("delay")
        # 死信设置
        arguments = self.set_delay(delay)
        # 声明队列
        result = self.channel.queue_declare(queue=queue, durable=self.queue_durable, arguments=arguments)
        # 声明交换机
        self.channel.exchange_declare(exchange=exchange, durable=self.exchange_durable, exchange_type=type)
        # 交换机绑定队列
        self.channel.queue_bind(exchange=exchange, queue=result.method.queue, routing_key=routing_key)
        # 设置prefetch_count
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(result.method.queue, callback, auto_ack=self.auto_ack)
        self.channel.start_consuming()

    def send_func(self, data):
        self.send_vail(data)
        exchange = data.get("exchange")
        routing_key = data.get("routing_key")
        type = data.get("type")
        msg = json.dumps(data.get("msg"))
        # 声明
        self.channel.exchange_declare(exchange=exchange, durable=self.exchange_durable, exchange_type=type)
        # 消息投掷到交换机
        self.channel.basic_publish(exchange=exchange, routing_key=routing_key, body=msg,
                                   properties=self.properties)
        self.connection.close()


class RabbitMqUtil(object):
    bin_param = {
        "work": RabbitMqConsumer,  # 生产者模式
        "fanout": RabbitMqFanout,  # 订阅模式
        "direct": RabbitMqDirect,  # 路由模式
        "topic": RabbitMqDirect,  # 主题模式
    }

    def __init__(self):
        self.mq_obj = None

    @staticmethod
    def maintain_heartbeat(mq_obj):
        while True:
            # print("----")
            mq_obj.connection.process_data_events()     # 发送心跳
            time.sleep(30)      # 每30秒发送一次心跳

    def bin_handle(self, data):
        if not data:
            raise Exception("缺少参数")
        type = data.get("type")
        if not type:
            raise Exception("缺少类型")
        mq_obj = self.bin_param.get(type)
        if not mq_obj:
            raise Exception("无此类型")
        self.mq_obj = mq_obj()
        self.mq_obj.bin_func(data)
        # heartbeat_thread = threading.Thread(target=self.maintain_heartbeat, args=(mq_obj,), daemon=True)
        # heartbeat_thread.start()

    def send_handle(self, data):
        if not data:
            raise Exception("缺少参数")
        type = data.get("type")
        if not type:
            raise Exception("缺少类型")
        mq_obj = self.bin_param.get(type)
        if not mq_obj:
            raise Exception("无此类型")
        mq_obj = mq_obj()
        mq_obj.send_func(data)

    def handel_error(self, fun):
        # 丢弃任务
        def wrapper(self, ch, method, properties, body):
            try:
                params = json.loads(body)
                logger.info(f"入参：{json.dumps(params, ensure_ascii=False)}")
                rsp = fun(self, ch, method, properties, body)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return rsp
            except Exception as e:
                logger.error(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}rabbit : {str(e)} , {str(traceback.format_exc())} body:{body}")
                ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)  # 不重试任务

        return wrapper

    def retry_err(self, fun):
        # 重试
        def wrapper(self, ch, method, properties, body):
            try:
                rsp = fun(self, ch, method, properties, body)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return rsp
            except Exception as e:
                logger.error(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}rabbit : {str(e)} body:{str(body)}")
                ch.basic_reject(delivery_tag=method.delivery_tag, requeue=True)  # 表示拒绝的消息将重新排队等待重新投递给其他消费者

        return wrapper

    def ack_err(self, fun):
        # 异常时，手动确认
        def wrapper(self, ch, method, properties, body):
            try:
                rsp = fun(self, ch, method, properties, body)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return rsp
            except Exception as e:
                logger.error(f"======手动异常：{str(e)}===========")
                # 手动确认
                ch.basic_ack(delivery_tag=method.delivery_tag)

        return wrapper
