"""Shared fixtures for the TigerGraph functional/database pytest suite.

Target selection: set TG_BASE (e.g. http://<m1-ip>:14240) or it is read from
infra/cluster.env (M1_IP). All tests talk to the standard RESTPP endpoints.
"""
import json
import os
import re
import pathlib

import pytest
import requests

REPO = pathlib.Path(__file__).resolve().parents[1]


def _default_base():
    env = os.environ.get("TG_BASE")
    if env:
        return env.rstrip("/")
    cluster_env = REPO / "infra" / "cluster.env"
    if cluster_env.exists():
        m = re.search(r"M1_IP=(\S+)", cluster_env.read_text())
        if m:
            return f"http://{m.group(1)}:14240"
    return "http://localhost:14240"


class FinGraphApi:
    """Thin helper over TigerGraph's RESTPP API for the finGraph graph."""

    def __init__(self, base):
        self.base = base
        self.graph = f"{base}/restpp/graph/finGraph"
        self.query = f"{base}/restpp/query/finGraph"
        self.s = requests.Session()

    # --- vertices -----------------------------------------------------
    def upsert_account(self, vid, balance):
        r = self.s.post(self.graph, timeout=10, data=json.dumps(
            {"vertices": {"Account": {vid: {"balance": {"value": balance}}}}}))
        return r.json()["results"][0]["accepted_vertices"]

    def upsert_person(self, pid, name):
        r = self.s.post(self.graph, timeout=10, data=json.dumps(
            {"vertices": {"Person": {pid: {"name": {"value": name}}}}}))
        j = r.json()
        return -1 if j.get("error") else j["results"][0]["accepted_vertices"]

    def get_account(self, vid):
        j = self.s.get(f"{self.graph}/vertices/Account/{vid}", timeout=10).json()
        if j.get("error") or not j.get("results"):
            return None
        return j["results"][0]["attributes"]

    def get_person_name(self, pid):
        j = self.s.get(f"{self.graph}/vertices/Person/{pid}", timeout=10).json()
        if j.get("error") or not j.get("results"):
            return None
        return j["results"][0]["attributes"]["name"]

    def delete_account(self, vid):
        return self.s.delete(f"{self.graph}/vertices/Account/{vid}", timeout=10).json()

    def delete_person(self, pid):
        return self.s.delete(f"{self.graph}/vertices/Person/{pid}", timeout=10).json()

    def raw_get_account(self, vid):
        return self.s.get(f"{self.graph}/vertices/Account/{vid}", timeout=10).json()

    # --- edges --------------------------------------------------------
    def upsert_transfer(self, src, dst, amount):
        r = self.s.post(self.graph, timeout=10, data=json.dumps(
            {"edges": {"Account": {src: {"TRANSFER": {"Account": {dst: {"amount": {"value": amount}}}}}}}}))
        return r.json()["results"][0]["accepted_edges"]

    def out_transfers(self, vid):
        j = self.s.get(f"{self.graph}/edges/Account/{vid}/TRANSFER", timeout=10).json()
        return [] if j.get("error") else j.get("results", [])

    # --- installed queries ---------------------------------------------
    def run_query(self, name, **params):
        return self.s.get(f"{self.query}/{name}", params=params, timeout=20).json()


@pytest.fixture(scope="session")
def api():
    return FinGraphApi(_default_base())


@pytest.fixture(scope="session")
def known_fixture(api):
    """A controlled fixture with hand-computable expected values.

    ftA=1000.00, ftB=2000.00, ftC=3000.50 and edges ftA->ftB, ftA->ftC, ftB->ftC.
    The installed helper query ftAgg() aggregates exactly these three vertices:
    count=3, sum=6000.50, count(balance>1500)=2.
    """
    ids = ("ftA", "ftB", "ftC")
    for v in ids:
        api.delete_account(v)
    api.upsert_account("ftA", 1000.00)
    api.upsert_account("ftB", 2000.00)
    api.upsert_account("ftC", 3000.50)
    api.upsert_transfer("ftA", "ftB", 100.00)
    api.upsert_transfer("ftA", "ftC", 200.00)
    api.upsert_transfer("ftB", "ftC", 50.00)
    yield {"ids": ids, "count": 3, "balance_sum": 6000.50, "over_1500": 2}
    for v in ids:
        api.delete_account(v)


@pytest.fixture
def scratch_accounts(api):
    """Per-test scratch vertex ids, cleaned up afterwards."""
    created = []
    yield created
    for vid in created:
        api.delete_account(vid)


@pytest.fixture
def scratch_persons(api):
    created = []
    yield created
    for pid in created:
        api.delete_person(pid)
