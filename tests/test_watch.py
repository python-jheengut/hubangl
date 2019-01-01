# -*- coding: utf-8 -*-

# This file is part of HUBAngl.
# HUBAngl Uses Broadcaster Angle
#
# HUBAngl is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# HUBAngl is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HUBAngl.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright (c) 2016-2019 David Testé

import unittest
import unittest.mock

from core import watch


class TestRemoteWatcher(unittest.TestCase):
    @unittest.mock.patch("core.watch.REMOTE_CHECK_FREQUENCY", .1)
    def setUp(self):
        watch.setup()
        self.watcher = watch.RemoteWatcher()
        self.address = ("::1", 8000)

    def tearDown(self):
        self.watcher.stop()
        watch.shutdown()

    @unittest.mock.patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_start(self, submit_mock):
        self.watcher.start()
        self.assertIsNotNone(self.watcher._watch_task)
        self.assertTrue(submit_mock.called_with_args(
            watch.RemoteWatcher._check_availability))

    @unittest.mock.patch("core.watch.REMOTE_CHECK_FREQUENCY", .3)
    @unittest.mock.patch("concurrent.futures.ThreadPoolExecutor.submit")
    def test_start_twice_does_nothing(self, submit_mock):
        self.watcher.start()
        self.watcher.start()
        self.assertEqual(submit_mock.call_count, 1)

    @unittest.mock.patch("core.watch.REMOTE_CHECK_FREQUENCY", .1)
    def test_stop(self):
        self.watcher.add_watcher(self.address)

        self.watcher.stop()
        # Does nothing if not started beforehand
        self.assertFalse(self.watcher._shutting_down)

        self.watcher.start()
        self.watcher.stop()
        self.assertTrue(self.watcher._shutting_down)
        self.assertIsNone(self.watcher._watch_task)
        # Watched elements are kept for the next start
        self.assertNotEqual(self.watcher._elements, {})

    def test_add_watcher(self):
        self.watcher.add_watcher(self.address)
        element = self.watcher._elements[self.address]
        self.assertTrue(isinstance(element, watch.RemoteElement))

        # Several call with the same argument does nothing
        self.watcher.add_watcher(self.address)
        self.assertEqual(len(self.watcher._elements), 1)
        self.assertIs(self.watcher._elements[self.address], element)

    def test_remove_watcher(self):
        self.watcher.add_watcher(self.address)

        self.watcher.remove_watcher(self.address)
        self.assertEqual(self.watcher._elements, {})


class TestRemoteElement(unittest.TestCase):
    # TODO:
    # Add system test for happy path with ping() method (need to spin up an
    # icecast server and having nmap install on the host)

    def setUp(self):
        self.element = watch.RemoteElement(("127.0.0.1", 8000))
        self.latency = 25

    def test_get_state(self):
        expected = {"available": False,
                    "unavailable_since": None,
                    "unknown_state": False,
                    "host_running": False,
                    "port_open": False,
                    "latency": -1}

        result = self.element.get_state()
        self.assertEqual(result, expected)

    def test_set_state_ping_succeed(self):
        expected = {"available": True,
                    "unavailable_since": None,
                    "unknown_state": False,
                    "host_running": True,
                    "port_open": True,
                    "latency": self.latency}

        self.element._set_state(True, True, self.latency)
        result = self.element.get_state()
        self.assertEqual(result, expected)

    def test_set_state_ping_failed_host_not_running(self):
        self.element._set_state(False, True, self.latency)
        result = self.element.get_state()

        self.assertFalse(result["available"])
        self.assertIsNotNone(result["unavailable_since"])
        self.assertFalse(result["host_running"])
        self.assertTrue(result["port_open"])
        self.assertEqual(result["latency"], self.latency)

    def test_set_state_ping_failed_port_closed(self):
        self.element._set_state(True, False, self.latency)
        result = self.element.get_state()

        self.assertFalse(result["available"])
        self.assertIsNotNone(result["unavailable_since"])
        self.assertTrue(result["host_running"])
        self.assertFalse(result["port_open"])
        self.assertEqual(result["latency"], self.latency)

    def _assert_in_unknown_state(self):
        result = self.element.get_state()

        self.assertTrue(result["unknown_state"])
        self.assertFalse(result["host_running"])
        self.assertFalse(result["port_open"])
        self.assertEqual(result["latency"], -1)

    @unittest.mock.patch("core.watch.REMOTE_PING_TIMEOUT", .1)
    def test_ping_timeout(self):
        self.element._ping_command = ["sleep", "100"]

        self.element.ping()
        self._assert_in_unknown_state()

    def test_ping_with_error_returned_from_command(self):
        self.element._ping_command = ["sleep", "spam"]

        self.element.ping()
        self._assert_in_unknown_state()