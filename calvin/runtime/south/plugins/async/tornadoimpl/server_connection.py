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

from calvin.utilities.calvinlogger import get_logger
_log = get_logger(__name__)

from tornado.tcpserver import TCPServer

class TornadoHTTPProtocol:

    def __init__(self, factory, actor_id, address):
        self.delimiter = '\r\n\r\n'
        self.data_available = False
        self.connection_lost = False
        self._header = None
        self._data_buffer = b""
        self._data = None
        self.factory = factory
        self._actor_id = actor_id
        self._expected_length = 0
        self._line_buffer = []
        self._stream = None
        self._address = address

    def lineReceived(self, line):
        line = line[0:len(line)-len(self.delimiter)]
        header = [h.strip() for h in line.split("\r\n")]
        self._command = header.pop(0)
        self._header = {}
        for attr in header:
            if len(attr) > 0:
                a, v = attr.split(':', 1)
                self._header[a.strip().lower()] = v.strip()
        self._expected_length = int(self._header.get('content-length', 0))
        if self._expected_length != 0:
            self._stream.read_bytes(self._expected_length, self.rawDataReceived)
        else:
            self.data_available = True
            self.factory.trigger()

    def rawDataReceived(self, data):
        self._data_buffer += data #[0:len(data)-len(self.delimiter)]

        if self._expected_length - len(self._data_buffer) == 0:
            self._data = self._data_buffer
            self._data_buffer = b""
            self.data_available = True
            self.factory.trigger()

    def send(self, data):
        self._stream.write(data, self.writtingComplete)

    def writtingComplete(self):
        if not self._stream.closed():
            self.close()

    def close(self):
        self._stream.close()

    def connectionLost(self):
        self.connection_lost = True
        if self._address in self.factory.addr2conn.keys():
            del self.factory.addr2conn[self._address]
            self.factory.connections.remove(self)
        self.factory.trigger()

    def setStream(self, stream):
        self._stream = stream
        stream.set_close_callback(self.connectionLost)

    def data_get(self):
        if self.data_available:
            command = self._command
            headers = self._header
            if command.lower().startswith("get "):
                data = b""
            else:
                data = self._data
            self._header = None
            self._data = None
            self.data_available = False
            self._expected_length = 0
            return command, headers, data
        raise Exception("Connection error: no data available")


class TornadoTcpServerWrapper(TCPServer):

    def __init__(self, factory, actor_id):
        super(TornadoTcpServerWrapper, self).__init__(max_buffer_size=factory.MAX_LENGTH)
        self.factory = factory
        self._actor_id = actor_id

    def _handle_connection(self, connection, address):
        protocol = None
        if self.factory.mode == 'line':
            protocol =  None
        elif self.factory.mode == 'raw':
            protocol = None
        elif self.factory.mode == 'http':
            protocol = TornadoHTTPProtocol(self.factory, actor_id=self._actor_id, address=address)
        self.factory.addr2conn[address] = protocol
        self.factory.pending_connections.append((address, protocol))
        self.factory.connections.append(protocol)
        super(TornadoTcpServerWrapper, self)._handle_connection(connection, address)
        self.factory.trigger()

    def handle_stream(self, stream, address):
        currentProtocol = self.factory.addr2conn[address]
        currentProtocol.setStream(stream)
        stream.read_until(currentProtocol.delimiter, currentProtocol.lineReceived)


class ServerProtocolFactory():
    def __init__(self, trigger=None, mode='http', delimiter='\r\n', max_length=8192, actor_id=None):
        self._trigger            = trigger
        self.mode                = mode
        self.delimiter           = delimiter
        self.MAX_LENGTH          = max_length
        self.connections         = []
        self.pending_connections = []
        self._actor_id           = actor_id
        self._tcpServer          = None
        self.addr2conn          = {}

    def trigger(self):
        self._trigger(actor_ids=[self._actor_id])

    def start(self, host, port):
        self._tcpServer = TornadoTcpServerWrapper(self, actor_id=self._actor_id)
        self._tcpServer.listen(port, address=host)
        #self._tcpServer.bind(port, address=host)
        #self._tcpServer.start(0)

    def stop(self):
        self._tcpServer.stop()
        del self.connections[:]
        self.addr2conn.clear()

    def accept(self):
        addr, conn = self.pending_connections.pop()
        if not self.pending_connections:
            self.connection_pending = False
        return addr, conn
