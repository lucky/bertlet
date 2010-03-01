#!/usr/bin/env python
import sys
import unittest
import mymodule
from os.path import abspath, dirname, join

# Adding the project path so we get the latest code, not what's installed
project_path = abspath(join(dirname(abspath(__file__)), '..'))
sys.path.insert(0, project_path)
from bertlet.server import Server, InvalidModule, InvalidFunction

class ServerTests(unittest.TestCase):

    def test_init(self):
        server = Server(port=2222)
        self.assertEqual(2222, server.port)
        self.assertEqual({}, server.module_registry)

    def test_dispatcher(self):
        server = Server()
        self.assertRaises(InvalidModule, server.dispatch, 'x', 'x')

        server.register(mymodule)
        self.assertRaises(InvalidFunction, server.dispatch, 'mymodule', 'x')

        server.register(mymodule, name='mod')
        self.assertRaises(InvalidFunction, server.dispatch, 'mod', 'x')

        self.assertEqual('lulz', server.dispatch('mod', 'foo'))
        self.assertEqual(10, server.dispatch('mod', 'bar', 5))
        self.assertEqual(25, server.dispatch('mod', 'bar', 5, 5))

if __name__ == '__main__':
    unittest.main()