import eventlet
import struct
import bert
import logging
import sys
import traceback
import zlib
from types import ModuleType
from bertlet.exceptions import *

bert_decode = bert.BERTDecoder().decode
bert_encode = bert.BERTEncoder().encode

call_atom = bert.Atom('call')
cast_atom = bert.Atom('cast')
reply_atom = bert.Atom('reply')
noreply_atom = bert.Atom('noreply')
error_atom = bert.Atom('error')
info_atom = bert.Atom('info')
encode_atom = bert.Atom('encoding')
gzip_atom = bert.Atom('gzip')
accept_encoding_atom = bert.Atom('accept_encoding')

GZIP_INFO_BERT = (info_atom, encode_atom, [(gzip_atom, )])
GZIP_ACCEPT_BERT = (info_atom, accept_encoding_atom, [(gzip_atom, )])

def create_berp(bert):
    return '%s%s' % (struct.pack('>I', len(bert)), bert)

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
        """
        raw_data is the actual bytestring of the request
        data is the decoded object, e.g. {request, 'foo', 'bar'}
        """
        self.client_connection = client_connection
        self.raw_data = extract_bert(self.client_connection.socket)
        self.data = bert_decode(self.raw_data)

class ClientConnection(object):
    def __init__(self, address, server):
        self.socket, address = address
        self.ip = address[0]
        self.server = server
        self.infos = []
        self.gzip_enabled = False
        self.gzip_encode = False
        if self.server.certfile:
            from eventlet.green.ssl import wrap_socket
            self.socket = wrap_socket(
                            self.socket,
                            server_side=True,
                            certfile=self.server.certfile,
                            keyfile=self.server.keyfile)
        logging.info("%s connected" % (address,))

    def loop(self):
        while 1:
            if not self.handle_request():
                return False

    def handle_request(self):
        try:
            request = Request(self)
            if request.data[0] == gzip_atom:
                if not self.gzip_encode:
                    raise ProtocolError, 'gzip encoding without info berp'
                logging.debug("Received gzipped data")
                request.raw_data = zlib.decompress(request.data[1])
                request.data = bert_decode(request.raw_data)

                self.gzip_encode = False
            response = self.create_response(request)
            if response:
                result_bert = bert_encode(response)
                gzip_info_berp = None
                if self.gzip_enabled and \
                        len(result_bert) >= self.server.gzip_threshold:
                    result_bert = bert_encode((gzip_atom, zlib.compress(result_bert)))
                    gzip_info_berp = create_berp(bert_encode(GZIP_INFO_BERT))
                    logging.debug("Gzipping return value")
                if gzip_info_berp:
                    self.socket.send(gzip_info_berp)
                self.socket.send(create_berp(result_bert))
            return True
        except CloseSession:
            return False

    def handle_info(self, command, options):
        if not isinstance(options, list):
            raise InvalidInfo, 'Options argument must be a list'
        if command == encode_atom:
            logging.debug("Received encode info")
            if options[0][0] != 'gzip':
                raise InvalidInfo, 'Unknown encode type'
            self.gzip_encode = True
            self.gzip_enabled = True
        elif command == accept_encoding_atom:
            logging.debug("Received accept encoding info")
            if options[0][0] != 'gzip':
                raise InvalidInfo, 'Unknown encode type'
            self.gzip_enabled = True
        self.infos.append((command, options))

    def create_response(self, request):
        req_type = request.data[0]

        if req_type in (call_atom, cast_atom):
            green = eventlet.spawn(self.server.dispatch, request)

            if req_type == call_atom:
                value = green.wait()
                if isinstance(value, tuple) and value[0] == error_atom:
                    return value
                response = (reply_atom, value)
            else:
                response = (noreply_atom,)

            return self.server.apply_response_middleware(response)
        elif req_type == info_atom:
            self.handle_info(*request.data[1:])
         
            

class Server(object):

    def __init__(self, port=2133, host=None, logfile=None, loglevel=logging.DEBUG,
                       certfile=None, keyfile=None, gzip_threshold=2048):
        self.module_registry = {}
        self.middleware = []
        self.port = port
        self.socket = None
        self.gzip_threshold = gzip_threshold  
        self.certfile = certfile
        self.keyfile = keyfile
        logging.basicConfig(filename=logfile, level=loglevel)

        if host is None:
            host = '127.0.0.1'
        self.host = host

    def apply_request_middleware(self, request):
        for m in self.middleware:
            if hasattr(m, 'process_request'):
                request = m.process_request(request)
                if not isinstance(request, Request):
                    return request

        return request

    def apply_response_middleware(self, response):
        for m in self.middleware:
            if hasattr(m, 'process_response'):
                response = m.process_response(response)

        return response

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
            name = module.__name__.split('.')[-1]

        self.module_registry[name] = module

    def dispatch(self, request):
        module_name, function_name, args = request.data[1:]
        try:
            request = self.apply_request_middleware(request)
            # Short circuit your mom
            if not isinstance(request, Request):
                return request
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

        if not callable(function) or function_name.startswith('_'):
            raise InvalidFunction, "No such function"

        return function(*args)
