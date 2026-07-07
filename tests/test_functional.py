"""Functional tests (FT1-FT12): the database works as intended under normal conditions.

CRUD, installed queries, traversal determinism, aggregation and filtering — every test
asserts an expected value against the actual API result.
"""
import pytest

pytestmark = pytest.mark.functional


class TestCrud:
    def test_FT01_create_vertex_accepted(self, api, scratch_accounts):
        scratch_accounts.append("ftD")
        assert api.upsert_account("ftD", 500.00) == 1

    def test_FT02_read_back_returns_correct_value(self, api, scratch_accounts):
        scratch_accounts.append("ftD2")
        api.upsert_account("ftD2", 500.00)
        assert api.get_account("ftD2")["balance"] == 500.00

    def test_FT03_update_in_place_not_duplicate(self, api, scratch_accounts):
        scratch_accounts.append("ftD3")
        api.upsert_account("ftD3", 500.00)
        api.upsert_account("ftD3", 750.25)          # same primary id -> update
        assert api.get_account("ftD3")["balance"] == 750.25

    def test_FT04_create_edge_accepted(self, api, scratch_accounts, known_fixture):
        scratch_accounts.append("ftD4")
        api.upsert_account("ftD4", 1.0)
        assert api.upsert_transfer("ftD4", "ftA", 42.00) == 1

    def test_FT05_out_edge_count_after_insert(self, api, scratch_accounts, known_fixture):
        scratch_accounts.append("ftD5")
        api.upsert_account("ftD5", 1.0)
        api.upsert_transfer("ftD5", "ftA", 42.00)
        assert len(api.out_transfers("ftD5")) == 1

    def test_FT06_upsert_dedup_no_duplicate_edge(self, api, scratch_accounts, known_fixture):
        scratch_accounts.append("ftD6")
        api.upsert_account("ftD6", 1.0)
        api.upsert_transfer("ftD6", "ftA", 42.00)
        api.upsert_transfer("ftD6", "ftA", 42.00)    # same edge again
        assert len(api.out_transfers("ftD6")) == 1

    def test_FT07_delete_vertex_gone(self, api):
        api.upsert_account("ftD7", 9.99)
        api.delete_account("ftD7")
        assert api.get_account("ftD7") is None


class TestQueries:
    def test_FT08_installed_query_getAccount(self, api):
        r = api.run_query("getAccount", acc="acc0")
        assert not r.get("error")
        assert r["results"][0]["S"][0]["v_id"] == "acc0"

    def test_FT09_khop_traversal_deterministic(self, api):
        first = api.run_query("kHopTransfers", acc="acc0", k=2)["results"][0]["reached"]
        second = api.run_query("kHopTransfers", acc="acc0", k=2)["results"][0]["reached"]
        assert first == second

    def test_FT10_aggregation_count(self, api, known_fixture):
        agg = api.run_query("ftAgg")["results"][0]
        assert agg["n"] == known_fixture["count"]

    def test_FT11_aggregation_sum_balance(self, api, known_fixture):
        agg = api.run_query("ftAgg")["results"][0]
        assert agg["bal"] == known_fixture["balance_sum"]

    def test_FT12_filtering_count_balance_over_1500(self, api, known_fixture):
        agg = api.run_query("ftAgg")["results"][0]
        assert agg["hi"] == known_fixture["over_1500"]
