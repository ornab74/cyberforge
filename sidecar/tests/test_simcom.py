import asyncio

from cyberforge_sidecar.simcom import SimComTerminal


def test_origin_command_refuses_simulated_attribution():
    result = asyncio.run(SimComTerminal().execute("origin"))
    joined = "\n".join(result.lines).lower()
    assert result.ok
    assert "not attributed" in joined
    assert "country" in joined
