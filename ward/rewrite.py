import ast
import inspect
import types
from typing import Iterable

from ward.expect import ExpectationFailed, Expected
from ward.testing import Test


class RewriteAssert(ast.NodeTransformer):
    def visit_Assert(self, node):
        if (
            isinstance(node.test, ast.Compare)
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.Eq)
        ):
            call = ast.Call(
                func=ast.Name(id="assert_equal", ctx=ast.Load()),
                args=[node.test.left, node.test.comparators[0]],
                keywords=[],
            )

            new_node = ast.Expr(value=call)
            ast.copy_location(new_node, node)
            ast.fix_missing_locations(new_node)
            return new_node

        return node


def rewrite_assertions_in_tests(tests: Iterable[Test]):
    return [rewrite_assertion(test) for test in tests]


def assert_equal(a, b):
    if a != b:
        raise ExpectationFailed("%r != %r" % (a, b), [
            Expected(
                this=a,
                op="==",
                that=b,
                success=False,
                op_args=(),
                op_kwargs={},
            )
        ])


def rewrite_assertion(test: Test):
    # Get the old code and code object
    code = inspect.getsource(test.fn)
    code_obj = test.fn.__code__

    # Rewrite the AST of the code
    tree = ast.parse(code)
    new_tree = RewriteAssert().visit(tree)

    # Reconstruct the test function
    new_code_obj = compile(new_tree, code_obj.co_filename, "exec")
    new_test_func = types.FunctionType(
        new_code_obj.co_consts[1],
        {"assert_equal": assert_equal, **(test.fn.__globals__)},
    )
    new_test_func.ward_meta = test.fn.ward_meta

    return Test(
        **{k: vars(test)[k] for k in vars(test) if k != "fn"},
        fn=new_test_func,
    )