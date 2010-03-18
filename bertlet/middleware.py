import bert

_a = bert.Atom

class InvalidAuth(Exception): pass

class BasicAuthMiddleware(object):
    """
    Expects request in format: {call, auth, authenticate, 'username', 'password'}
    You MUST define your own authenticate method.
    """
    @classmethod
    def process_request(cls, request):
        conn = request.client_connection

        if getattr(conn, 'authed', False):
            return request

        if (request.data[:3] != (_a('call'), _a('auth'), _a('authenticate'))) or len(request.data) != 4:
            raise InvalidAuth, 'Expected auth request!'

        conn.authed = cls.authenticate(request.data[3][0], request.data[3][1])
        if not conn.authed:
            raise InvalidAuth, "Could not authenticate the user"

        return True

    @classmethod
    def authenticate(cls, username, password):
        raise NotImplementedError, 'authenticate method not implemented'

