"""
tamper_evident_ledger.py

A lightweight, append-only, cryptographically hash-chained and signed ledger
for the biochar dMRV engine. Gives you tamper-evidence (any retroactive edit
breaks the chain and the signature) without running blockchain infrastructure.

Drop-in usage from your existing Python calc engine:

    from tamper_evident_ledger import HashChainLedger

    ledger = HashChainLedger("ledger/dmrv_ledger.jsonl", key_path="ledger/signing_key.pem")

    # after computing a batch in your engine:
    entry = ledger.append(
        record_type="PyrolysisBatch",
        record_id=batch_id,
        data=batch_output_dict,   # the actual computed row / dict you'd write to Sheets
    )

    # anytime, to check nothing has been altered:
    ok, issues = ledger.verify_chain()
"""

from __future__ import annotations

import json
import hashlib
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


GENESIS_HASH = "0" * 64


def _canonical_json(obj: Any) -> str:
    """Deterministic JSON serialization so the same data always hashes the same way."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class LedgerEntry:
    seq: int
    record_type: str          # e.g. "FeedstockLot", "PyrolysisBatch", "BiocharBatch", "FieldApplication"
    record_id: str            # your existing batch_id / lot_id
    timestamp: str            # ISO-8601 UTC
    data_hash: str            # sha256 of the canonicalized data payload
    prev_hash: str            # hash of the previous entry (chain link)
    entry_hash: str           # hash of this entry's own content (seq+type+id+ts+data_hash+prev_hash)
    signature: str            # hex signature of entry_hash, signed with the ledger's private key

    def to_json(self) -> str:
        return _canonical_json(asdict(self))


class HashChainLedger:
    """
    Append-only ledger backed by a JSON-Lines file. Each entry:
      - hashes the actual data payload (data_hash)
      - links to the previous entry's hash (prev_hash) -> forms the chain
      - is signed with an Ed25519 key -> proves who wrote it and blocks forgery

    Tampering with any past entry (or reordering, or deleting one) breaks the
    hash chain from that point forward and invalidates its signature -- both
    are checked in verify_chain().
    """

    def __init__(self, ledger_path: str, key_path: str | None = None):
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

        self.key_path = Path(key_path) if key_path else self.ledger_path.parent / "signing_key.pem"
        self._private_key = self._load_or_create_key(self.key_path)
        self._public_key = self._private_key.public_key()

    # ---------- key management ----------

    def _load_or_create_key(self, key_path: Path) -> Ed25519PrivateKey:
        if key_path.exists():
            with open(key_path, "rb") as f:
                return serialization.load_pem_private_key(f.read(), password=None)
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        key_path.parent.mkdir(parents=True, exist_ok=True)
        with open(key_path, "wb") as f:
            f.write(pem)
        os.chmod(key_path, 0o600)
        return key

    def export_public_key_pem(self) -> bytes:
        """Share this with a VVB or auditor so they can independently verify signatures."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    # ---------- core append ----------

    def _last_entry(self) -> LedgerEntry | None:
        if not self.ledger_path.exists() or self.ledger_path.stat().st_size == 0:
            return None
        with open(self.ledger_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            pos = f.tell()
            chunk = b""
            while pos > 0:
                pos -= 1
                f.seek(pos)
                b = f.read(1)
                if b == b"\n" and chunk:
                    break
                chunk = b + chunk
            last_line = chunk.decode("utf-8").strip()
        if not last_line:
            return None
        d = json.loads(last_line)
        return LedgerEntry(**d)

    def append(self, record_type: str, record_id: str, data: dict) -> LedgerEntry:
        """
        Commit a new record (e.g. a batch calculation output) to the ledger.
        `data` should be the actual dict/row you're about to write to your
        Google Sheet or CSV -- this hashes and signs exactly that payload.
        """
        prev = self._last_entry()
        seq = (prev.seq + 1) if prev else 0
        prev_hash = prev.entry_hash if prev else GENESIS_HASH

        timestamp = datetime.now(timezone.utc).isoformat()
        data_hash = _sha256_hex(_canonical_json(data))

        header = _canonical_json({
            "seq": seq,
            "record_type": record_type,
            "record_id": record_id,
            "timestamp": timestamp,
            "data_hash": data_hash,
            "prev_hash": prev_hash,
        })
        entry_hash = _sha256_hex(header)
        signature = self._private_key.sign(bytes.fromhex(entry_hash)).hex()

        entry = LedgerEntry(
            seq=seq,
            record_type=record_type,
            record_id=record_id,
            timestamp=timestamp,
            data_hash=data_hash,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            signature=signature,
        )

        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(entry.to_json() + "\n")

        return entry

    # ---------- verification ----------

    def verify_chain(self) -> tuple[bool, list[str]]:
        """
        Walk the entire ledger and confirm:
          1) each entry's hash chain matches (prev_hash == previous entry_hash)
          2) each entry's own entry_hash matches its recomputed content hash
          3) each entry's signature is valid for that entry_hash
        Returns (is_valid, list_of_problem_descriptions).
        """
        issues: list[str] = []
        if not self.ledger_path.exists():
            return True, []

        prev_hash = GENESIS_HASH
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                entry = LedgerEntry(**d)

                header = _canonical_json({
                    "seq": entry.seq,
                    "record_type": entry.record_type,
                    "record_id": entry.record_id,
                    "timestamp": entry.timestamp,
                    "data_hash": entry.data_hash,
                    "prev_hash": entry.prev_hash,
                })
                recomputed_hash = _sha256_hex(header)

                if entry.prev_hash != prev_hash:
                    issues.append(f"line {lineno}: chain break -- prev_hash does not match previous entry")
                if entry.entry_hash != recomputed_hash:
                    issues.append(f"line {lineno}: entry content does not match its own hash (edited after write)")
                try:
                    self._public_key.verify(bytes.fromhex(entry.signature), bytes.fromhex(entry.entry_hash))
                except InvalidSignature:
                    issues.append(f"line {lineno}: signature invalid (not signed by this ledger's key)")

                prev_hash = entry.entry_hash

        return (len(issues) == 0), issues

    def verify_record_matches(self, record_id: str, data: dict) -> bool:
        """
        Given a data payload you have NOW (e.g. re-pulled from your Sheet),
        confirm it still matches what was originally committed for record_id.
        Use this to detect if someone edited a Sheet row after the fact.
        """
        target_hash = _sha256_hex(_canonical_json(data))
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                if d["record_id"] == record_id:
                    return d["data_hash"] == target_hash
        raise KeyError(f"record_id {record_id} not found in ledger")

    def get_audit_trail(self, record_id: str) -> list[dict]:
        """Return every ledger entry touching a given record_id, in order."""
        trail = []
        if not self.ledger_path.exists():
            return trail
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                if d["record_id"] == record_id:
                    trail.append(d)
        return trail


if __name__ == "__main__":
    # quick self-test / demo
    ledger = HashChainLedger("demo_ledger/dmrv_ledger.jsonl")

    e1 = ledger.append("FeedstockLot", "LOT-2026-001", {
        "species": "Prosopis juliflora", "biomass_kg": 1820, "gee_run_id": "gee_run_88a",
    })
    e2 = ledger.append("PyrolysisBatch", "BATCH-2026-001", {
        "input_lot_ids": ["LOT-2026-001"], "kiln_id": "K-03", "yield_kg": 410, "h_corg": 0.41,
    })

    ok, issues = ledger.verify_chain()
    print("Chain valid:", ok, issues)

    # simulate tampering: hand-edit the file
    with open("demo_ledger/dmrv_ledger.jsonl", "r") as f:
        lines = f.readlines()
    tampered = json.loads(lines[0])
    tampered["data_hash"] = "deadbeef" * 8
    lines[0] = json.dumps(tampered) + "\n"
    with open("demo_ledger/dmrv_ledger.jsonl", "w") as f:
        f.writelines(lines)

    ok2, issues2 = ledger.verify_chain()
    print("Chain valid after tampering:", ok2, issues2)
