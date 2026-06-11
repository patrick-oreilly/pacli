from pacli.policy import Policy


async def test_policy_requires_approval_for_high_risk_tools():
    policy = Policy()

    assert policy.requires_approval("execute_shell")
    assert not policy.requires_approval("read_file")
