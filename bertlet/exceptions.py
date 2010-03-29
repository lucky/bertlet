class ProtocolError(Exception):
    "The interface to reportable errors"
    error_code = -99
    error_type = 'unknown'

class BadHeader(ProtocolError):
    error_code = 1
    error_type = 'protocol'

class BadData(ProtocolError):
    error_code = 2
    error_type = 'protocol'

class InvalidModule(ProtocolError):
    error_code = 1
    error_type = 'server'
    
class InvalidFunction(ProtocolError):
    error_code = 2
    error_type = 'server'

class InvalidInfo(ProtocolError): pass
class CloseSession(Exception): pass
