"""Database / data-correctness tests (DT1-DT7): reads, writes, types, structure."""
import pytest

pytestmark = pytest.mark.database


def test_DT01_read_after_write_consistency(api, scratch_accounts):
    scratch_accounts.append("ftE")
    api.upsert_account("ftE", 111.11)
    assert api.get_account("ftE")["balance"] == 111.11


def test_DT02_query_result_determinism(api):
    runs = [api.run_query("getAccount", acc="acc5")["results"][0]["S"][0]["v_id"]
            for _ in range(3)]
    assert runs == ["acc5", "acc5", "acc5"]


def test_DT03_double_precision_round_trip(api, scratch_accounts):
    scratch_accounts.append("ftF")
    api.upsert_account("ftF", 123.456789)
    assert api.get_account("ftF")["balance"] == 123.456789


def test_DT04_edge_attribute_round_trip(api, scratch_accounts, known_fixture):
    scratch_accounts.append("ftG")
    api.upsert_account("ftG", 0.0)
    api.upsert_transfer("ftG", "ftA", 987.65)
    amounts = [e["attributes"]["amount"] for e in api.out_transfers("ftG")]
    assert amounts == [987.65]


def test_DT05_referential_integrity_edge_target_exists(api, known_fixture):
    assert api.get_account("ftA") is not None


def test_DT06_controlled_out_edge_count_exact(api, scratch_accounts, known_fixture):
    scratch_accounts.append("ftH")
    api.upsert_account("ftH", 0.0)
    api.upsert_transfer("ftH", "ftA", 1.0)
    assert len(api.out_transfers("ftH")) == 1


def test_DT07_missing_vertex_clean_error(api):
    j = api.raw_get_account("does_not_exist_zzz")
    assert j.get("error") is True          # clean error flag, not a crash
