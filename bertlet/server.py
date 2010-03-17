import eventlet
import struct
import bert
import logging
import sys
import traceback
from types import ModuleType
from bertlet.exceptions import *

bert_decode = bert.BERTDecoder().decode
bert_encode = bert.BERTEncoder().encode

call_atom = bert.Atom('call')
cast_atom = bert.Atom('cast')
reply_atom = bert.Atom('reply')
noreply_atom = bert.Atom('noreply')
error_atom = bert.Atom('error')

def create_berp(value):
    bert = bert_encode(value)
    berp = '%s%s' % (struct.pack('>I', len(bert)), bert)
    return berp

def extract_bert(socket):
    headers = socket.recv(4)
    if not headers:
        raise CloseSession

    # big endian; not specified by protocol, but by testing with canonical
    # Ruby client library. Tom Preston-Werner ain't nuthin' to fuck with.
    length = struct.unpack(">I", headers)[0]
    return socket.recv(length)

def generate_error(etype, value, backtrace):
    error_type = bert.Atom(getattr(etype, 'error_type', 'user'))
    error_code = getattr(etype, 'error_code', 100)
    return (error_atom, (
        error_type,
        error_code,
        etype.__name__,
        str(value.args[0]), # We can only assume the first exception argument
                            # is the message
        traceback.format_tb(backtrace),
    ))

class Request(object):
    def __init__(self, client_connection):
        self.client_connection = client_connection
        self.raw_data = extract_bert(self.client_connection.conn)
        self.data = bert_decode(self.raw_data)

class ClientConnection(object):
    def __init__(self, address, server):
        self.conn, address = address
        self.ip = address[0]
        self.server = server
        logging.info("%s connected" % (address,))

    def loop(self):
        while 1:
            if not self.handle_request():
                return False

    def handle_request(self):
        try:
            response = self.create_response(Request(self))
            self.conn.send(create_berp(response))
            return True
        except CloseSession:
            return False

    def create_response(self, request):
        req_type, args = request.data[0], request.data[1:]

        if req_type in (call_atom, cast_atom):
            module, function, function_args = args
            green = eventlet.spawn(self.server.dispatch, module, function, *function_args)

            if req_type == call_atom:
                value = green.wait()
                if isinstance(value, tuple) and value[0] == error_atom:
                    return value
                return (reply_atom, value)
            else:
                return (noreply_atom,)

class Server(object):

    def __init__(self, port=2133, host=None, logfile=None, loglevel=logging.DEBUG):
        self.module_registry = {}
        self.port = port
        self.socket = None
        logging.basicConfig(filename=logfile, level=loglevel)

        if host is None:
            host = '127.0.0.1'
        self.host = host

    def run(self):
        self.socket = eventlet.listen((self.host, self.port))
        logging.info("Listening on %s:%s" % (self.host, self.port))
        try:
            while 1:
                eventlet.spawn_n(self.serve_client, self.socket.accept())
        except KeyboardInterrupt:
            return True

    def serve_client(self, address):
        return ClientConnection(address, self).loop()

    def register(self, module, name=None):
        assert isinstance(module, ModuleType)
        if name is None:
            name = module.__name__

        self.module_registry[name] = module

    def dispatch(self, module_name, function_name, *args):
        try:
            return self._dispatch(module_name, function_name, *args)
        except (Exception,), e:
            etype, evalue, etraceback = sys.exc_info()
            logging.warning("Error when attempting to call %s.%s: %s" % (
                module_name, function_name, e)
            )
            logging.debug(traceback.format_exc())
            return generate_error(etype, evalue, etraceback)

    def _dispatch(self, module_name, function_name, *args):
        if module_name not in self.module_registry:
            raise InvalidModule, "No such module"

        module = self.module_registry[module_name]
        function = getattr(module, function_name, None)

        if not callable(function):
            raise InvalidFunction, "No such function"

        return function(*args)
