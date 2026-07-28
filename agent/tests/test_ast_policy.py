import pytest

from yuanqi_agent.security.ast_policy import AstPolicyViolation, AstSecurityChecker

SAFE_ANALYSIS = """
import pandas as pd

frame = pd.DataFrame(input_data)
result = {"total": float(frame["amount"].sum())}
chart = {"title": "Sales", "xAxis": ["total"], "series": [result["total"]]}
"""


def test_accepts_bounded_in_memory_pandas_analysis() -> None:
    AstSecurityChecker().validate(SAFE_ANALYSIS)


@pytest.mark.parametrize(
    "source",
    [
        "import os\nresult = os.getcwd()",
        "result = open('secret.txt').read()",
        "import pandas as pd\nresult = pd.read_csv('secret.csv')",
        "result = ().__class__.__base__.__subclasses__()",
        "result = eval('1 + 1')",
        "import subprocess\nresult = 1",
    ],
)
def test_rejects_escape_and_io_primitives(source: str) -> None:
    with pytest.raises(AstPolicyViolation):
        AstSecurityChecker().validate(source)


def test_checker_resets_state_between_validations() -> None:
    checker = AstSecurityChecker()
    with pytest.raises(AstPolicyViolation):
        checker.validate("import os\nresult = 1")
    checker.validate("result = 1")
