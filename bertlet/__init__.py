from bertlet.server import Server

def serve(*modules, **kwargs):
    server = Server(**kwargs)
    for mod in modules:
        server.register(mod)

    server.run()
