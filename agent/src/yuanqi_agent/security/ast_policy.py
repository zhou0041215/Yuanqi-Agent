import ast
from dataclasses import dataclass, field

from yuanqi_agent.errors import AgentError


@dataclass(frozen=True, slots=True)
class AstPolicy:
    allowed_modules: frozenset[str] = frozenset(
        {"pandas", "numpy", "math", "statistics", "datetime", "decimal", "collections"}
    )
    max_source_bytes: int = 50_000
    max_nodes: int = 5_000
    max_string_length: int = 20_000
    required_result_names: frozenset[str] = field(default_factory=lambda: frozenset({"result"}))


class AstPolicyViolation(AgentError):
    def __init__(self, violations: list[str]):
        super().__init__(
            "AST_POLICY_VIOLATION",
            "Generated code violates the sandbox AST policy",
            status_code=422,
            details=violations,
        )
        self.violations = violations


class AstSecurityChecker(ast.NodeVisitor):
    _forbidden_call_names = frozenset(
        {
            "open",
            "eval",
            "exec",
            "compile",
            "__import__",
            "input",
            "breakpoint",
            "getattr",
            "setattr",
            "delattr",
            "globals",
            "locals",
            "vars",
            "dir",
            "help",
            "memoryview",
        }
    )
    _forbidden_attributes = frozenset(
        {
            "system",
            "popen",
            "spawn",
            "fork",
            "execv",
            "execve",
            "connect",
            "socket",
            "urlopen",
            "request",
            "read_csv",
            "read_excel",
            "read_feather",
            "read_fwf",
            "read_hdf",
            "read_html",
            "read_json",
            "read_orc",
            "read_parquet",
            "read_pickle",
            "read_sas",
            "read_spss",
            "read_sql",
            "read_sql_query",
            "read_sql_table",
            "read_stata",
            "read_table",
            "read_xml",
            "to_csv",
            "to_excel",
            "to_feather",
            "to_hdf",
            "to_html",
            "to_json",
            "to_orc",
            "to_parquet",
            "to_pickle",
            "to_sql",
            "to_stata",
            "to_xml",
        }
    )
    _forbidden_nodes = (
        ast.AsyncFunctionDef,
        ast.Await,
        ast.ClassDef,
        ast.Global,
        ast.Nonlocal,
        ast.Yield,
        ast.YieldFrom,
    )

    def __init__(self, policy: AstPolicy | None = None):
        self.policy = policy or AstPolicy()
        self.violations: list[str] = []
        self.node_count = 0
        self.assigned_names: set[str] = set()

    def validate(self, source: str) -> ast.Module:
        self.violations = []
        self.node_count = 0
        self.assigned_names = set()
        if len(source.encode("utf-8")) > self.policy.max_source_bytes:
            raise AstPolicyViolation(["source exceeds the configured size limit"])
        try:
            tree = ast.parse(source, mode="exec")
        except SyntaxError as exc:
            raise AstPolicyViolation([f"syntax error at line {exc.lineno}: {exc.msg}"]) from exc
        self.visit(tree)
        missing = self.policy.required_result_names - self.assigned_names
        if missing:
            self.violations.append("code must assign: " + ", ".join(sorted(missing)))
        if self.violations:
            raise AstPolicyViolation(self.violations)
        return tree

    def generic_visit(self, node: ast.AST) -> None:
        self.node_count += 1
        if self.node_count > self.policy.max_nodes:
            self.violations.append("AST node count exceeds the configured limit")
            return
        if isinstance(node, self._forbidden_nodes):
            self.violations.append(
                f"line {getattr(node, 'lineno', '?')}: {type(node).__name__} is forbidden"
            )
        super().generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_module(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            self.violations.append(f"line {node.lineno}: relative imports are forbidden")
        self._check_module(node.module or "", node.lineno)
        for alias in node.names:
            if alias.name == "*" or alias.name.startswith("_"):
                self.violations.append(f"line {node.lineno}: unsafe import target '{alias.name}'")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in self._forbidden_call_names:
            self.violations.append(f"line {node.lineno}: call to '{node.func.id}' is forbidden")
        if isinstance(node.func, ast.Attribute):
            self._check_attribute(node.func.attr, node.lineno)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._check_attribute(node.attr, node.lineno)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("_"):
            self.violations.append(f"line {node.lineno}: private name access is forbidden")
        if isinstance(node.ctx, (ast.Store, ast.Param)):
            self.assigned_names.add(node.id)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, (str, bytes)) and len(node.value) > self.policy.max_string_length:
            self.violations.append(f"line {node.lineno}: literal exceeds the configured size limit")
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant):
            exponent = node.right.value
            if isinstance(exponent, (int, float)) and abs(exponent) > 1_000:
                self.violations.append(f"line {node.lineno}: exponent is too large")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.decorator_list:
            self.violations.append(f"line {node.lineno}: function decorators are forbidden")
        self.generic_visit(node)

    def _check_module(self, module: str, line: int) -> None:
        root = module.split(".", maxsplit=1)[0]
        if root not in self.policy.allowed_modules:
            self.violations.append(f"line {line}: import of module '{module}' is forbidden")

    def _check_attribute(self, attribute: str, line: int) -> None:
        if attribute.startswith("_") or attribute in self._forbidden_attributes:
            self.violations.append(f"line {line}: attribute '{attribute}' is forbidden")
