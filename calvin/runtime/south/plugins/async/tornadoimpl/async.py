# -*- coding: utf-8 -*-

# Copyright (c) 2015 Ericsson AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import tornado
from tornado.ioloop import IOLoop

class DelayedCall(object):

    def __init__(self, delay, callback, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self.delay = delay
        self.callback = callback
        self.reset()

    def reset(self):
        self.timeout = IOLoop.instance().call_later(self.delay, self.callback, *self._args, **self._kwargs)

    def active(self):
        if self.timeout:
            return True

    def cancel(self):
        if self.timeout:
            IOLoop.instance().remove_timeout(self.timeout)

def run_ioloop():
    IOLoop.instance().start()


def stop_ioloop():
    IOLoop.instance().stop()


# Thread function
#call_from_thread = IOLoop
