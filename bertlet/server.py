import eventlet
import struct
import bert
from types import ModuleType

bert_decode = bert.BERTDecoder().decode
bert_encode = bert.BERTEncoder().encode

call_atom = bert.Atom('call')
cast_atom = bert.Atom('cast')
reply_atom = bert.Atom('reply')
noreply_atom = bert.Atom('noreply')

def create_berp(value):
    bert = bert_encode(value)
    berp = '%s%s' % (struct.pack('>I', len(bert)), bert)
    return berp

class InvalidModule(StandardError): pass
class InvalidFunction(StandardError): pass
class CloseSession(StandardError): pass

class Request(object):
    def __init__(self, client_connection):
        self.client_connection = client_connection
        self.get_headers()
        self.get_data()

    def get_headers(self):
        # BERP header is 4 bytes
        headers = self.client_connection.conn.recv(4)
        if not headers:
            raise CloseSession

        # Big-endian!
        self.length = struct.unpack(">I", headers)[0]

    def get_data(self):
        self.raw_data = self.client_connection.conn.recv(self.length)
        self.data = bert_decode(self.raw_data)

class ClientConnection(object):
    def __init__(self, address, server):
        self.conn, address = address
        self.ip = address[0]
        self.server = server
        #print "Address is:"
        #print address

    def loop(self):
        while 1:
            if not self.handle_request():
                return False

    def handle_request(self):
        try:
            request = Request(self)
            self.send_response(request.data)
            return True
        except CloseSession:
            return False

    def send_response(self, request):
        req_type, args = request[0], request[1:]

        if req_type in (call_atom, cast_atom):
            module, function, function_args = args
            green = eventlet.spawn(self.server.dispatch, module, function, *function_args)

            if req_type == call_atom:
                response = (reply_atom, green.wait())
            else:
                response = (noreply_atom,)

        self.conn.send(create_berp(response))


class Server(object):

    def __init__(self, port=2133, host=None):
        self.module_registry = {}
        self.port = port
        if host is None:
            self.host = '127.0.0.1'
        else:
            self.host = host
        self.socket = None

    def run(self):
        self.socket = eventlet.listen((self.host, self.port))
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
        if module_name not in self.module_registry:
            raise InvalidModule

        module = self.module_registry[module_name]
        function = getattr(module, function_name, None)

        if not callable(function):
            raise InvalidFunction

        return function(*args)
