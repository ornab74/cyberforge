import asyncio

from cyberforge_sidecar.amccs import decompose, fuse, render_simcom_terminal, run_amccs
from cyberforge_sidecar.datapull import parse_datapull_command
from cyberforge_sidecar.simcom import SimComTerminal


def test_parse_datapull_flags():
    parsed = parse_datapull_command(
        ["datapull", "origin", "of", "regional", "outage", "--mode", "single", "--provider", "offline"]
    )
    assert parsed["topic"] == "origin of regional outage"
    assert parsed["mode"] == "single"
    assert parsed["provider"] == "offline"


def test_decompose_has_sim_forensics_shard():
    shards = decompose("origin of regional outage")
    ids = {s.shard_id for s in shards}
    assert "sim_forensics" in ids
    assert "attribution_sim" in ids


def test_amccs_offline_datapull_renders_simcom():
    result = asyncio.run(
        run_amccs(
            "origin of regional outage",
            mode="single",
            provider="offline",
            include_remote=False,
            command="./datapull origin of regional outage",
        )
    )
    joined = "\n".join(result["lines"])
    assert result["ok"]
    assert "AEGIS-816 SIMCOM TERMINAL" in joined
    assert "DATAPULL RESULT" in joined
    assert "SIMULATED FORENSICS" in joined
    assert "STATUS: DATAPULL COMPLETE" in joined
    sf = result["fused"]["sim_forensics"]
    assert sf.get("entry_vector")
    assert sf.get("simulated_source_country")


def test_simcom_datapull_command():
    term = SimComTerminal()
    result = asyncio.run(
        term.execute("./datapull origin of regional outage --mode single --provider offline")
    )
    joined = "\n".join(result.lines)
    assert result.ok
    assert "DATAPULL COMPLETE" in joined
    assert result.payload is not None
    assert result.payload.get("calibre") == "SIM_FORENSIC"


def test_simcom_predictive_entry_vector():
    term = SimComTerminal()
    result = asyncio.run(
        term.execute(
            "simcom entry_vector --mode predictive --scope twin_alpha --engine dyson_gamma"
        )
    )
    joined = "\n".join(result.lines).lower()
    assert result.ok
    assert "predictive" in joined
    assert "entry vector" in joined


def test_origin_forensic_boundary_still_default():
    result = asyncio.run(SimComTerminal().execute("origin"))
    joined = "\n".join(result.lines).lower()
    assert result.ok
    assert "not attributed" in joined
