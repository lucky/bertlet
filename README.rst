=============================
Bertlet, BERT-RPC in Eventlet
=============================

Bertlet is a Python implementation of the BERT-RPC_ protocol written in
Eventlet_ to make concurrency trivial.

**Warning: Bertlet is in early stages of development.** It does not yet cover
the entire BERT-RPC_ protocol. See the Roadmap_ for more information.

Features
--------

Bertlet is at version 0.2. Current features supported:

 - BERT-RPC_ cast and call
 - SSL
 - Middleware
 - Gzip
 - Preliminary informational berp support
 - "Private" functions are not accessible; anything beginning with an underscore
 - Protocol error handling
 
See Roadmap_ for upcoming features.

Requirements
------------

 - Eventlet_ >= 0.9.5
 - python-bert_

Optional:

 - ssl (either Python >= 2.6 or pyopenssl)

Usage
-----

Bertlet is intended to be incredibly easy to use. BERT-RPC_ uses modules and
functions to expose functionality; Bertlet uses Python modules and functions
in the same manner. Creating a service with Bertlet is a two-step process: 
create your modules and functions, then expose them with a ``Server`` object.

Example module ``foo.py``::

    def bar():
        return "Hello, world!"
        
Example server runner::

    #!/usr/bin/env python
    from bertlet import serve
    import foo

    serve(foo, certfile="mycert.crt", keyfile="mycert.key")
    
It's that simple. Your BERT-RPC_ service is now running on 2133 with the 
``foo`` module exposing the ``bar`` function. **Note**: this example also shows how
SSL is used.

Roadmap
-------

This roadmap is subject to change. Just like your mom.
 
0.3
 - Caching directives
 
0.4
 - Streaming binary support

0.5 - ???

0.6 - ???
 
0.7
 - Multiprocess support
 
0.8
 - API stability for 1.0 release
 - Full API documentation

0.9
 - Full test coverage

1.0
 - "Stable" release with full BERT-RPC 1.0 support
 
Bugs and Code Submissions
=========================

If you find a bug, please let me know! If you wish to contribute, please note
that while I accept patches, it is possible that I will modify the changes
before I integrate them into the trunk.

License
=======

Bertlet is released under the MIT License. Please see the LICENSE file for
the full text of the license.

.. _BERT-RPC: http://bert-rpc.org/
.. _Eventlet: http://eventlet.net/
.. _python-bert: http://github.com/samuel/python-bert
