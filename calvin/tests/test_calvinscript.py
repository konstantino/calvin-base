# -*- coding: utf-8 -*-

# Copyright (c) 2015 Ericsson AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from calvin.csparser.parser import calvin_parser
from calvin.csparser.codegen import generate_app_info
import unittest
import json
import difflib
import pytest

def absolute_filename(filename):
    import os.path
    return os.path.join(os.path.dirname(__file__), filename)


class CalvinTestBase(unittest.TestCase):

    def setUp(self):
        self.test_script_dir = absolute_filename('scripts/')

    def tearDown(self):
        pass

    def _read_file(self, file):
        try:
            with open(file, 'r') as source:
                text = source.read()
        except Exception as e:
            print "Error: Could not read file: '%s'" % file
            raise e
        return text

    def _format_unexpected_error_message(self, errors):
        msg_list = ["Expected empty error, not {0}".format(err) for err in errors]
        return '\n'.join(msg_list)

    def parse(self, test, source_text=None, verify=True):
        if not source_text:
            test = self.test_script_dir + test + '.calvin'
            source_text = self._read_file(test)

        ast, parser_issues, _ = calvin_parser(source_text, test)
        app_info, codegen_issues = generate_app_info(ast, name=test, verify=verify)
        issues = parser_issues + codegen_issues

        errors = [issue for issue in issues if issue['type'] == 'error']
        errors = sorted(errors, key=lambda x : x['reason'])

        warnings = [issue for issue in issues if issue['type'] == 'warning']
        warnings = sorted(warnings, key=lambda x : x['reason'])

        return app_info, errors, warnings



class CalvinScriptCheckerTest(CalvinTestBase):
    """Test the CalvinsScript checker"""

    def testCheckSimpleScript(self):
        script = """
        a:std.CountTimer()
        b:io.Print()

        a.integer > b.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertFalse(errors)

    def testCheckSimpleScript2(self):
        script = """
        a:Foo()
        b:Bar()
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertTrue(errors)

    def testCheckLocalComponent(self):
        script = """
        component Foo() -> out {
            f:std.CountTimer()
            f.integer > .out
        }
        a:Foo()
        b:io.StandardOut()
        a.out > b.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertFalse(errors)

    def testCheckOutportConnections(self):
        script = """
        a:std.CountTimer()
        b:std.CountTimer()
        c:io.StandardOut()
        a.integer > c.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(errors[0]['reason'], "Actor b (std.CountTimer) is missing connection to outport 'integer'")

    def testCheckInportConnections1(self):
        script = """
        c:io.StandardOut()
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['reason'], "Actor c (io.StandardOut) is missing connection to inport 'token'")

    def testCheckInportConnections2(self):
        script = """
        a:std.CountTimer()
        b:std.CountTimer()
        c:io.StandardOut()
        a.integer > c.token
        b.integer > c.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0]['reason'], "Actor c (io.StandardOut) has multiple connections to inport 'token'")

    def testBadComponent1(self):
        script = """
        component Foo() -> out {
            a:std.CountTimer()
            b:std.CountTimer()
            a.integer > .out
        }
        a:Foo()
        b:io.StandardOut()
        a.out > b.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['reason'], "Actor b (std.CountTimer) is missing connection to outport 'integer'")

    def testBadComponent2(self):
        script = """
        component Foo() -> out {
            a:std.CountTimer()
            b:io.StandardOut()
            a.integer > b.token
        }
        a:Foo()
        b:io.StandardOut()
        a.out > b.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['reason'], "Component Foo is missing connection to outport 'out'")

    def testBadComponent3(self):
        script = """
        component Foo() -> out {
            a:std.CountTimer()
            a.integer > .out
            a.integer > .out
        }
        a:Foo()
        b:io.StandardOut()
        a.out > b.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0]['reason'], "Component Foo has multiple connections to outport 'out'")
        self.assertEqual(errors[1]['reason'], "Component Foo has multiple connections to outport 'out'")

    def testBadComponent4(self):
        script = """
        component Foo() in -> {
            a:io.StandardOut()
        }
        b:Foo()
        a:std.CountTimer()
        a.integer > b.in
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0]['reason'], "Actor a (io.StandardOut) is missing connection to inport 'token'")
        self.assertEqual(errors[1]['reason'], "Component Foo is missing connection to inport 'in'")

    def testBadComponent5(self):
        script = """
        component Foo() in -> {
            a:io.StandardOut()
            .foo > a.token
        }
        b:Foo()
        a:std.CountTimer()
        a.integer > b.in
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0]['reason'], "Component Foo has no inport 'foo'")
        self.assertEqual(errors[1]['reason'], "Component Foo is missing connection to inport 'in'")

    def testBadComponent6(self):
        script = """
        component Foo() -> out {
            a:std.CountTimer()
            a.integer > .foo
        }
        b:Foo()
        a:io.StandardOut()
        b.out > a.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0]['reason'], "Component Foo has no outport 'foo'")
        self.assertEqual(errors[1]['reason'], "Component Foo is missing connection to outport 'out'")

    def testBadComponent7(self):
        script = """
        component Foo() in -> out {
            .in > .out
        }
        """
        result, errors, warnings = self.parse('inline', script)
        print errors
        self.assertEqual(len(errors), 3)
        self.assertEqual(errors[0]['reason'], "Component Foo is missing connection to inport 'in'")
        self.assertEqual(errors[1]['reason'], "Component Foo is missing connection to outport 'out'")
        self.assertEqual(errors[2]['reason'], "Component inport connected directly to outport.")



    def testUndefinedActors(self):
        script = """
        a.token > b.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0]['reason'], "Undefined actor: 'a'")
        self.assertEqual(errors[1]['reason'], "Undefined actor: 'b'")


    def testUndefinedArguments(self):
        script = """
        a:std.Constant()
        b:io.StandardOut()
        a.token > b.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['reason'], "Missing argument: 'data'")

    def testExcessArguments(self):
        script = """
        a:std.Constant(data=1, bar=2)
        b:io.StandardOut()
        a.token > b.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['reason'], "Excess argument: 'bar'")


    def testComponentUndefinedArgument(self):
        script = """
        component Foo(file) in -> {
            a:io.StandardOut()
            .in > a.token
        }
        b:Foo()
        a:std.CountTimer()
        a.integer > b.in
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0]['reason'], "Missing argument: 'file'")
        self.assertEqual(errors[1]['reason'], "Unused argument: 'file'")

    def testComponentUnusedArgument(self):
        script = """
        component Foo(file) in -> {
            a:io.StandardOut()
            .in > a.token
        }
        b:Foo(file="Foo.txt")
        a:std.CountTimer()
        a.integer > b.in
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['reason'], "Unused argument: 'file'")

    def testComponentExcessArgument(self):
        script = """
        component Foo(file) -> out {
            file > .out
        }
        a:Foo(file="Foo.txt", bar=1)
        b:io.Print()
        a.out > b.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['reason'], "Excess argument: 'bar'")


    def testLocalComponentRecurse(self):
        script = """
          component E() in -> out {
          f:std.Identity()

          .in > f.token
          f.token > .out
        }
        component B() in -> out {
          e:E()

          .in > e.in
          e.out > .out
        }

        a:std.Counter()
        b:B()
        c:io.StandardOut()

        a.integer > b.in
        b.out > c.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 0)

    def testLocalComponentBad(self):
        script = """
        component B() in -> out {
          e:E()

          .in > e.in
          e.out > .out
        }
        component E() in -> out {
          f:std.Identity()

          .in > f.token
          f.token > .out
        }

        a:std.Counter()
        b:B()
        c:io.StandardOut()

        a.integer > b.in
        b.out > c.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 0)

    def testNoSuchPort(self):
        script = """
        i:std.Identity()
        src:std.CountTimer()
        dst:io.StandardOut()
        src.integer > i.foo
        i.bar > dst.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 4)
        self.assertEqual(errors[0]['reason'], "Actor i (std.Identity) has no inport 'foo'")
        self.assertEqual(errors[1]['reason'], "Actor i (std.Identity) has no outport 'bar'")
        self.assertEqual(errors[2]['reason'], "Actor i (std.Identity) is missing connection to inport 'token'")
        self.assertEqual(errors[3]['reason'], "Actor i (std.Identity) is missing connection to outport 'token'")

    def testRedfineInstance(self):
        script = """
        i:std.Identity()
        src:std.CountTimer()
        dst:io.StandardOut()
        i:std.RecTimer()
        src.integer > i.token
        i.token > dst.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['reason'], "Instance identifier 'i' redeclared")

    def testUndefinedActorInComponent(self):
        script = """
        component Bug() -> out {
          b.out > .out
        }
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)


    def testUndefinedConstant(self):
        script = """
        src : std.Constant(data=FOO)
        snk : io.StandardOut()
        src.token > snk.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['reason'], "Undefined identifier: 'FOO'")

    @pytest.mark.xfail()
    def testUnusedConstant(self):
        script = """
        define FOO=2
        sink : std.Terminator()
        1 > sink.void
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['reason'], "Unused constant: 'FOO'")


    def testDefinedConstant(self):
        script = """
        define FOO = 42
        src : std.Constant(data=FOO)
        snk : io.StandardOut()
        src.token > snk.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 0)

    def testUndefinedRecursiveConstant(self):
        script = """
        define FOO = BAR
        src : std.Constant(data=FOO)
        snk : io.StandardOut()
        src.token > snk.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0]['reason'], "Constant 'BAR' is undefined")
        self.assertEqual(errors[1]['reason'], "Undefined identifier: 'FOO'")


    def testDefinedRecursiveConstant(self):
        script = """
        define FOO = BAR
        define BAR = 42
        src : std.Constant(data=FOO)
        snk : io.StandardOut()
        src.token > snk.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 0)


    def testLiteralOnPort(self):
        script = """
        snk : io.StandardOut()
        42 > snk.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 0)

    def testComponentArgumentOnInternalPort(self):
        script = """
        component Foo(foo) -> out {
            foo > .out
        }
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 0)

    def testLiteralOnInternalPort(self):
        script = """
        component Foo() -> out {
            1 > .out
        }
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 0)


    def testBadLocalPort(self):
        script = """
        component Foo() in -> {
            snk : io.StandardOut()
            .in > snk.token
        }
        src : std.Counter()
        src.integer > .in
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['reason'], "Internal port '.in' outside component definition")


    def testVoidOnInPort(self):
        script = """
        iip : std.Init(data="ping")
        print : io.Print()
        void > iip.in
        iip.out > print.token
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 0)

    def testVoidOnOutPort(self):
        script = """
        src : std.Counter()
        src.integer > void
        """
        result, errors, warnings = self.parse('inline', script)
        self.assertEqual(len(errors), 0)


