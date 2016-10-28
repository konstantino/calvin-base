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

from concurrent import futures
from tornado.concurrent import run_on_executor
from tornado.testing import gen_test, AsyncTestCase

from calvin.runtime.south.plugins.async import async
from calvin.runtime.south.plugins.async import server_connection
from calvin.utilities.calvinlogger import get_logger

import pytest
import socket
_log = get_logger(__name__)

#TODO: would be nice to add a piece of code here that switches the framework to tornado for the sake of testing

def print_header(string):
    _log.info("\n\n### %s ###", string)

# Stub
class Scheduler_stub(object):
    def trigger_loop(self, actor_ids=None):
        """ Trigger the loop_once """
        async.DelayedCall(0, self.trigger_loop)
        return

@pytest.mark.gen_test
class TestTornadoServer(AsyncTestCase):
    executor = futures.ThreadPoolExecutor(2)

    @run_on_executor
    def connect(self, s, host, port):
        s.connect((host, port) )

    @run_on_executor
    def send(self, s, data):
        s.send(data)

    @run_on_executor
    def data_available(self, conn):
        first_print = True
        while conn.data_available is False:
            if first_print:
                print "waiting for conn.data_available ... ",
                first_print = False
        print "data available"
        return True

    @run_on_executor
    def connection_made(self, factory=None):
        first_print = True
        while not factory.connections:
            if first_print:
                print "waiting for connection ... ",
                first_print = False
        print "connection available"
        return True

    @run_on_executor
    def no_more_connections(self, factory):
        first_print = True
        while factory.connections:
            if first_print:
                print "waiting for connections to close ... ",
                first_print = False
        print ""
        return True

    @run_on_executor
    def close(self, sck):
        sck.close()

    @run_on_executor
    def hundred_connection_made(self, factory):
        first_print = True
        while not len(factory.connections) == self.numberOfConnections:
            if first_print:
                print "waiting for", self.numberOfConnections, "connection(s) ... ",
                first_print = False
        print ""
        return True

    @gen_test
    def test_many_clients(self):
        print_header("TEST_MANY_CLIENTS")
        print_header("Setup")
        scheduler = Scheduler_stub()
        self.factory = server_connection.ServerProtocolFactory(scheduler.trigger_loop)
        self.factory.start('localhost', 8123)

        self.numberOfConnections = 100

        print_header("Test_Connection")
        ##################################################################
        clients = []
        for i in range(self.numberOfConnections):
            clients.append(socket.socket(socket.AF_INET, socket.SOCK_STREAM))

        for c in clients:
            yield self.connect(c, 'localhost', 8123)

        yield self.hundred_connection_made(self.factory)

        assert len(self.factory.pending_connections) == self.numberOfConnections

        msg = "POST /deploy HTTP/1.1\r\nHost: localhost:5001\r\nContent-Length: 24\r\nUser-Agent: python-requests/2.9.1\r\n" \
              "Connection: keep-alive\r\nAccept: */*\r\nAccept-Encoding: gzip, deflate\r\n\r\n{\"app_info\": \"some_app\"}"

        for c in reversed(clients):
            _, conn = self.factory.accept()

            yield self.send(c, msg)

            yield self.data_available(conn)

            command, headers, data = conn.data_get()

            print command, headers, data

            yield self.close(c)

        assert not self.factory.pending_connections

    @gen_test
    def test_http_mode(self):
        print_header("TEST_HTTP_MODE")
        print_header("Setup")
        scheduler = Scheduler_stub()
        self.factory = server_connection.ServerProtocolFactory(scheduler.trigger_loop)

        self.factory.start('localhost', 8123)
        self.conn = None
        sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        print_header("Test_Connection")
        ##################################################################
        assert not self.factory.connections
        assert not self.factory.pending_connections

        #original code - doesn't work with tornado
        #yield threads.defer_to_thread(self.client_socket.connect, (('localhost', 8123)))

        #this worked
        yield self.connect(sck, 'localhost', 8123)

        #original code
        #yield threads.defer_to_thread(connection_made, self.factory)

        #instead
        yield self.connection_made(self.factory)

        assert self.factory.pending_connections

        _, self.conn = self.factory.accept()

        assert not self.factory.pending_connections

        ####################################################################
        ####################################################################

        #print_header("Test_Line_Received")
        ####################################################################
        assert self.conn.data_available is False

        #original code
        #yield threads.defer_to_thread(self.client_socket.send, "sending string \r\n")

        #this worked
        yield self.send(sck, "GET /id HTTP/1.1\r\nHost: localhost:5001\r\nConnection: keep-alive\r\nAccept-Encoding: gzip, deflate\r\nAccept: */*\r\nUser-Agent: python-requests/2.9.1\r\n\r\n")
        #original code
        #yield threads.defer_to_thread(data_available, self.conn)

        #instead
        yield self.data_available(self.conn)

        command, headers, data = self.conn.data_get()

        assert command.startswith("GET")

        assert len(headers) == 5

        assert data == ""

        #self.conn.send(sck, "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS\r\nAccess-Control-Allow-Origin: *\r\n\r\n")

        #msg = sck.recv(4096)

        #assert msg.startswith("HTTP")

        #sck.close()

        #assert not self.factory.connections

        #print_header("Teardown")
        self.factory.stop()

        #original code
        #yield threads.defer_to_thread(no_more_connections, self.factory)

        #instead
        yield self.no_more_connections(self.factory)
