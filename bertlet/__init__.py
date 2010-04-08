from bertlet.server import Server

__version__ = '0.2.3'

def serve(*modules, **kwargs):
    server = Server(**kwargs)
    for mod in modules:
        server.register(mod)

    server.run()
