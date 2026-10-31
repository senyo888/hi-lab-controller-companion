"""Pure wire/state/clock and asynchronous persistence-failure model tests."""
import asyncio
from copy import deepcopy
import hashlib
import hmac
import unittest

from observation_fixtures import p, r, SECRET, INSTANCE, EPOCH, NOW, Clock, payload, selected


class ProtocolTests(unittest.TestCase):
    def test_wire_window_allows_engine_clock_tolerance_only(self):
        for offset in (-2.001, 902.001):
            value = payload(state="COMPLETED")
            sample = value['campaign']['checkpoints'][1]
            sample['observed_at'] = p.iso(p.timestamp(sample['due_at']) + offset)
            p.validate(value)
        for offset in (-2.01, 902.01):
            sample['observed_at'] = p.iso(p.timestamp(sample['due_at']) + offset)
            with self.assertRaises(p.Invalid): p.validate(value)
        value = payload(state="RUNNING")
        value['campaign']['checkpoints'][0]['observed_at'] = p.iso(p.timestamp(value['campaign']['started_at']) - .001)
        with self.assertRaises(p.Invalid): p.validate(value)

    def test_idle_selection_and_two_domains(self):
        for domain in ("humidity_intelligence", "example_lighting"):
            value = payload(domain=domain)
            self.assertEqual(p.verify(p.sign(value, SECRET), SECRET, INSTANCE, EPOCH), value)

    def test_all_outcomes_and_distinct_terminal_selection(self):
        for state in p.STATES:
            value = payload(state=state)
            p.validate(value)
            if state in p.TERMINAL:
                value["selected_profile"] = selected("example_lighting")
                p.validate(value)
        value = payload(state="RUNNING");value["selected_profile"] = selected("example_lighting")
        with self.assertRaises(p.Invalid):p.validate(value)

    def test_pass_cannot_have_incomplete_or_failed_checkpoints(self):
        for change in (lambda c:c.update(completed_slots=8),
                       lambda c:c["checkpoints"][0].update(state="UNHEALTHY"),
                       lambda c:c.update(reasons=["CHECK_FAILED"]),
                       lambda c:c.update(state="RUNNING"),
                       lambda c:c.update(finished_at=c['started_at']),
                       lambda c:c.update(finished_at=None)):
            value = payload(state="COMPLETED");change(value["campaign"])
            with self.assertRaises(p.Invalid):p.validate(value)

    def test_closed_privilege_and_legacy_fields_refuse(self):
        for field in ("credentials", "entity_id", "target", "deployment_id", "confirmation_token", "command", "readiness"):
            value = payload();value[field] = "forbidden"
            with self.assertRaises(p.Invalid):p.validate(value)

    def test_bad_signature_pairing_and_ack(self):
        value = payload();raw = p.sign(value, SECRET)
        for secret,instance,epoch in (("b"*64,INSTANCE,EPOCH),(SECRET,EPOCH,EPOCH),(SECRET,INSTANCE,INSTANCE)):
            with self.assertRaises(p.Invalid):p.verify(raw,secret,instance,epoch)
        ack = p.acknowledgement(raw,value,SECRET);p.verify_ack(ack,raw,value,SECRET)
        with self.assertRaises(p.Invalid):p.verify_ack(ack,b"other",value,SECRET)

    def test_noncanonical_malformed_oversized_and_duplicates(self):
        for raw in (b"", b"[]", b"{}\n", b'{"a":1,"a":1}', b'{"a":NaN}', b"["*4000,
                    b"a"*(p.MAX_BYTES+1), b"\xff"):
            with self.subTest(raw=raw[:12]),self.assertRaises(p.Invalid):p.parse(raw)

    def test_boolean_sequence_oversized_ttl_and_future_checkpoint_refuse(self):
        for change in (lambda v:v.update(sequence=True),lambda v:v.update(expires_at=p.iso(NOW+61)),
                       lambda v:v["campaign"]["checkpoints"][0].update(observed_at=p.iso(NOW+1)),
                       lambda v:v["campaign"]["checkpoints"][0].update(slot=1)):
            value=payload(state="RUNNING");change(value)
            with self.assertRaises(p.Invalid):p.validate(value)


class ReceiverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock=Clock();self.saved=[]
        async def persist(record):self.saved.append(deepcopy(record))
        self.persist=persist
        self.receiver=self.make(r.initial_record(INSTANCE,EPOCH,SECRET))
    def make(self, record, persist=None):
        return r.Receiver(INSTANCE,EPOCH,SECRET,record,persist or self.persist,
            wall=lambda:self.clock.now,monotonic=lambda:self.clock.mono)
    async def receive(self, value=None):
        value=value or payload(now=self.clock.now)
        return await self.receiver.receive(p.sign(value,SECRET))

    async def test_commit_before_ack_and_original_expiry(self):
        self.clock.advance(20)
        raw=p.sign(payload(),SECRET);reply=await self.receiver.receive(raw)
        self.assertEqual(len(self.saved),1);p.verify_ack(reply,raw,payload(),SECRET)
        self.assertEqual(self.receiver.snapshot()["feed"],"fresh")
        self.clock.advance(40)
        self.assertEqual(self.receiver.snapshot()["feed"],"stale")

    async def test_replay_does_not_extend_or_clear_valid_message(self):
        await self.receive(payload(5))
        for value in (payload(5),payload(4),payload(5,now=NOW+1)):
            with self.assertRaises(p.Invalid):await self.receive(value)
        self.assertEqual(len(self.saved),1)
        self.assertEqual(self.receiver.snapshot()["feed"],"fresh")
        self.clock.advance(60);self.assertEqual(self.receiver.snapshot()["feed"],"stale")

    async def test_restart_requires_higher_sequence_and_no_restored_current(self):
        await self.receive(payload(7))
        self.receiver=self.make(self.saved[-1])
        self.assertEqual(self.receiver.snapshot()["feed"],"unavailable")
        with self.assertRaises(p.Invalid):await self.receive(payload(7))
        await self.receive(payload(9));self.assertEqual(self.receiver.snapshot()["feed"],"fresh")

    async def test_concurrent_requests_are_refused_while_persistence_pending(self):
        gate=asyncio.Event()
        async def persist(record):await gate.wait();self.saved.append(record)
        self.receiver=self.make(r.initial_record(INSTANCE,EPOCH,SECRET),persist)
        task=asyncio.create_task(self.receive());await asyncio.sleep(0)
        with self.assertRaisesRegex(p.Invalid,"RECEIVER_BUSY"):await self.receive(payload(2))
        self.assertIsNone(self.receiver.snapshot()["document"])
        gate.set();await task

    async def test_persistence_failure_poison_no_ack_or_retry(self):
        async def fail(record):raise OSError("synthetic disk failure")
        self.receiver=self.make(r.initial_record(INSTANCE,EPOCH,SECRET),fail)
        with self.assertRaisesRegex(p.Invalid,"CUSTODY_WRITE_FAILED"):await self.receive()
        self.assertIsNone(self.receiver.snapshot()["document"])
        with self.assertRaises(p.Invalid):await self.receive(payload(2))

    async def test_expiry_during_persistence_commits_floor_but_not_current(self):
        async def slow(record):self.saved.append(record);self.clock.advance(60)
        self.receiver=self.make(r.initial_record(INSTANCE,EPOCH,SECRET),slow)
        with self.assertRaises(p.Invalid):await self.receive()
        self.assertEqual(self.receiver.value["sequence"],1)
        self.assertIsNone(self.receiver.snapshot()["document"])

    async def test_clock_reversal_and_jump_never_revive(self):
        await self.receive();self.clock.advance(10);self.receiver.snapshot()
        self.clock.now-=1
        self.assertEqual(self.receiver.snapshot()["error"],"CLOCK_DISCONTINUITY")
        self.clock.now+=1
        with self.assertRaises(p.Invalid):await self.receive(payload(2,now=self.clock.now))

    async def test_future_expired_absent_selection_and_source_unavailable(self):
        for now in (NOW+6,NOW-60):
            with self.assertRaises(p.Invalid):await self.receive(payload(now=now))
        value=payload();value["selected_profile"]=None;await self.receive(value)
        self.assertEqual(self.receiver.snapshot()["error"],"SELECTION_UNAVAILABLE")
        value=payload(2);value["background_state"]="UNAVAILABLE";await self.receive(value)
        self.assertEqual(self.receiver.snapshot()["error"],"SOURCE_UNAVAILABLE")

    async def test_terminal_history_is_distinct_after_expiry_and_restart(self):
        value=payload(state="COMPLETED");await self.receive(value)
        original=self.receiver.snapshot()["terminal"]["campaign"]["finished_at"]
        self.clock.advance(60)
        self.assertIsNone(self.receiver.snapshot()["document"])
        self.receiver=self.make(self.saved[-1])
        self.assertEqual(self.receiver.snapshot()["terminal"]["campaign"]["finished_at"],original)
        await self.receive(payload(2,now=self.clock.now,domain="example_lighting"))
        self.assertEqual(self.receiver.snapshot()["terminal"]["campaign"]["domain"],"example_integration")

    async def test_closed_receiver_and_missing_corrupt_or_foreign_custody(self):
        self.receiver.close()
        with self.assertRaises(p.Invalid):await self.receive()
        for record in (None,{},r.initial_record(INSTANCE,INSTANCE,SECRET),
                       {**r.initial_record(INSTANCE,EPOCH,SECRET),"signature":"bad"}):
            with self.assertRaises(p.Invalid):self.make(record)


if __name__=="__main__":unittest.main()
