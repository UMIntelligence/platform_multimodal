#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import random

import time


class Snowflake:
    def __init__(self, worker_id, datacenter_id):
        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = 0
        self.last_timestamp = -1

    def _gen_timestamp(self):
        return int(time.time() * 1000)

    def _next_sequence(self, timestamp):
        if timestamp == self.last_timestamp:
            self.sequence = (self.sequence + 1) & 4095
            if self.sequence == 0:
                timestamp = self._til_next_millis()
        else:
            self.sequence = 0

        self.last_timestamp = timestamp
        return ((timestamp - 1420041600000) << 22) | (self.datacenter_id << 17) | (self.worker_id << 12) | self.sequence

    def _til_next_millis(self):
        timestamp = self._gen_timestamp()
        while timestamp <= self.last_timestamp:
            timestamp = self._gen_timestamp()
        return timestamp

    def generate(self):
        # print(self._gen_timestamp())
        timestamp = self._gen_timestamp()
        if timestamp < self.last_timestamp:
            raise Exception("Clock moved backwards, refuse to generate id")
        return self._next_sequence(timestamp)


sf = Snowflake(10, 10)


def set_flow():
    order_list = []
    count = 1
    while True:
        if count > 9:
            break
        num = str(count) + str(sf.generate())
        order_list.append(num)
        count += 1
    return random.choice(order_list)

