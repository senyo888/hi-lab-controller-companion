"""Real installed HA library, disposable storage and real loopback HTTP tests.

This is not the user's running HA, installed companion or rendered dashboard.
HTTP authentication middleware uses a synthetic test principal. HA's view wrapper,
our admin guard, body reader, coordinator, storage and sensors are real code.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import importlib
import json
import os
import sys
from pathlib import Path
import tempfile
import threading
import time
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest import mock

if importlib.util.find_spec("homeassistant") is None:
    raise unittest.SkipTest("HA adapter tests require the pinned Home Assistant validation environment")

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry, ConfigEntryState

from observation_fixtures import PACKAGE, p, SECRET, INSTANCE, EPOCH, payload

o = importlib.import_module(PACKAGE + ".observation")
s = importlib.import_module(PACKAGE + ".observation_sensor")


def entry(options):
    return ConfigEntry(version=1,minor_version=1,domain="hi_lab_controller",title="Synthetic controller",
        data={"shared_secret":"synthetic-only"},options=options,source="user",unique_id=None,
        discovery_keys=MappingProxyType({}),subentries_data=[],state=ConfigEntryState.SETUP_IN_PROGRESS)


class HAAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # The custody contract rejects writable ancestors such as Linux /tmp.
        # Use a fresh owner-only fixture below the private user home; never relax
        # production guards or change permissions on shared runner directories.
        self.temp=tempfile.TemporaryDirectory(prefix="hilc-ha-adapter-", dir=Path.home().resolve())
        # Resolve any platform-specific aliases before exercising real custody.
        self.root=Path(self.temp.name).resolve()
        self.hass=HomeAssistant(str(self.root))
        self.options={o.ENABLED:True,o.INSTANCE:INSTANCE,o.EPOCH:EPOCH,o.SECRET:SECRET}
        self.coordinators=[];self.clients=[]
    async def asyncTearDown(self):
        for client in self.clients:await client.close()
        for coordinator in self.coordinators:
            coordinator.stop();await coordinator.async_shutdown()
        await self.hass.async_stop(force=True)
        self.temp.cleanup()
    async def coordinator(self, options=None):
        coordinator=o.ObservationCoordinator(self.hass,entry(options if options is not None else self.options))
        self.coordinators.append(coordinator)
        await coordinator.initialize()
        return coordinator
    async def pair(self):
        await o.prepare_pairing(self.hass,self.options,{})
        return await self.coordinator()

    async def test_absent_pairing_creates_no_storage_or_network(self):
        coordinator=await self.coordinator({})
        self.assertEqual(coordinator.current()["error"],"NOT_PAIRED")
        self.assertFalse((self.root/'.storage').exists())

    async def test_pairing_real_private_store_restart_and_missing_custody(self):
        coordinator=await self.pair()
        value=payload(now=time.time());await coordinator.receive(p.sign(value,SECRET))
        store=o.storage(self.hass,INSTANCE,EPOCH)
        path=Path(store.path)
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        record=await store.async_load();self.assertEqual(record['value']['sequence'],1)
        coordinator.stop()
        second=await self.coordinator()
        self.assertEqual(second.current()['error'],'AWAITING_NEW_SEQUENCE')
        with self.assertRaises(p.Invalid):await second.receive(p.sign(value,SECRET))
        path.rename(path.with_suffix('.retained'))
        third=await self.coordinator()
        self.assertEqual(third.current()['error'],'PAIRING_CUSTODY_UNAVAILABLE')
        with self.assertRaises(p.Invalid):await o.prepare_pairing(self.hass,self.options,self.options)

    async def test_fsync_failure_is_not_acknowledged(self):
        coordinator=await self.pair()
        with mock.patch(PACKAGE+'.observation_storage.os.fsync',side_effect=OSError('synthetic fsync failure')):
            with self.assertRaises(p.Invalid):await coordinator.receive(p.sign(payload(now=time.time()),SECRET))
        self.assertEqual(coordinator.current()['error'],'CUSTODY_WRITE_FAILED')
        self.assertIsNone(coordinator.current()['document'])

    async def test_writable_config_ancestor_refuses_before_custody_creation(self):
        for mode in (0o720, 0o702, 0o777):
            with self.subTest(mode=oct(mode)):
                self.root.chmod(mode)
                try:
                    with self.assertRaisesRegex(p.Invalid, 'CUSTODY_INVALID'):
                        await o.prepare_pairing(self.hass,self.options,{})
                    self.assertFalse((self.root/'.hi_lab_controller').exists())
                finally:
                    self.root.chmod(0o700)

    async def test_wrong_permissions_hardlink_and_symlink_refuse(self):
        await o.prepare_pairing(self.hass,self.options,{})
        store=o.storage(self.hass,INSTANCE,EPOCH);path=Path(store.path)
        path.chmod(0o644)
        with self.assertRaises(p.Invalid):await store.async_load()
        path.chmod(0o600);alias=path.with_suffix('.alias');os.link(path,alias)
        with self.assertRaises(p.Invalid):await store.async_load()
        alias.unlink();retained=path.with_suffix('.retained');path.rename(retained);path.symlink_to(retained)
        with self.assertRaises(p.Invalid):await store.async_load()

    async def test_parent_substitution_writes_nothing_to_foreign_directory(self):
        for kind in ('directory','symlink'):
            options={**self.options,o.EPOCH:str(__import__('uuid').uuid4())}
            await o.prepare_pairing(self.hass,options,{})
            store=o.storage(self.hass,options[o.INSTANCE],options[o.EPOCH])
            record=await store.async_load();parent=store.path.parent
            retained=parent.with_name('retained-'+kind);parent.rename(retained)
            if kind=='symlink':parent.symlink_to(retained,target_is_directory=True)
            else:parent.mkdir(mode=0o700)
            with self.assertRaises(p.Invalid):await store.async_save(record)
            if kind=='directory':
                self.assertEqual(list(parent.iterdir()),[]);parent.rmdir()
            else:parent.unlink()
            retained.rename(parent)

    async def test_stage_substitution_cannot_overwrite_accepted_record(self):
        await self.pair()
        store=o.storage(self.hass,INSTANCE,EPOCH);record=await store.async_load()
        original=store.path.read_bytes();fsync=os.fsync;changed=[]
        def substitute(fd):
            fsync(fd)
            if not changed:
                stages=list(store.path.parent.glob('.pending-*'))
                if stages:
                    stages[0].unlink();stages[0].write_bytes(b'foreign');stages[0].chmod(0o600);changed.append(True)
        with mock.patch(PACKAGE+'.observation_storage.os.fsync',substitute):
            with self.assertRaises(p.Invalid):await store.async_save(record)
        self.assertTrue(changed);self.assertEqual(store.path.read_bytes(),original)

    async def test_cancelled_request_unload_drains_physical_write_before_reload(self):
        coordinator=await self.pair()
        module=importlib.import_module(PACKAGE+'.observation_storage')
        original=module.VerifiedStore._write
        entered=threading.Event();release=threading.Event()
        def held(store,record,initialize=False):
            entered.set();release.wait(3);return original(store,record,initialize)
        with mock.patch.object(module.VerifiedStore,'_write',held):
            request=asyncio.create_task(coordinator.receive(p.sign(payload(7,now=time.time()),SECRET)))
            await asyncio.to_thread(entered.wait,1)
            request.cancel()
            closing=asyncio.create_task(coordinator.async_close())
            await asyncio.sleep(.02);self.assertFalse(closing.done())
            release.set()
            with self.assertRaises(p.Invalid):await request
            await closing
        successor=await self.coordinator()
        self.assertEqual(successor.receiver.value['sequence'],7)
        with self.assertRaises(p.Invalid):await successor.receive(p.sign(payload(6,now=time.time()),SECRET))

    async def test_real_entities_independent_from_legacy_and_original_expiry(self):
        coordinator=await self.pair()
        self.hass.data[o.RUNTIME_DATA]={'synthetic':SimpleNamespace(observation=coordinator,coordinator=None)}
        value=payload(now=time.time(),state='RUNNING')
        await coordinator.receive(p.sign(value,SECRET))
        sensors={e.key:e for e in s.entities(coordinator)}
        self.assertEqual(sensors['observation_campaign'].native_value,'RUNNING')
        self.assertEqual(sensors['observation_campaign'].extra_state_attributes['campaign']['completed_slots'],1)
        self.assertTrue(sensors['observation_integration'].available)
        coordinator.receiver.deadline=time.monotonic()-1
        self.assertFalse(sensors['observation_campaign'].available)
        self.assertEqual(sensors['observation_campaign'].extra_state_attributes,{})
        self.assertEqual(sensors['observation_feed'].native_value,'stale')

    async def test_exact_expiry_timer_unloads_without_reviving(self):
        coordinator=await self.pair()
        value=payload(now=time.time());value['expires_at']=p.iso(time.time()+0.08)
        await coordinator.receive(p.sign(value,SECRET))
        self.assertIsNotNone(coordinator.expiry_cancel)
        await asyncio.sleep(.1)
        self.assertEqual(coordinator.current()['feed'],'stale')
        coordinator.stop();self.assertIsNone(coordinator.expiry_cancel)
        with self.assertRaises(p.Invalid):await coordinator.receive(p.sign(payload(2,now=time.time()),SECRET))

    async def test_loopback_endpoint_auth_size_replay_and_no_legacy_services(self):
        coordinator=await self.pair()
        self.hass.data[o.RUNTIME_DATA]={'synthetic':SimpleNamespace(observation=coordinator)}
        view=o.ObservationView(self.hass)
        @web.middleware
        async def authenticate(request,handler):
            auth=request.headers.get('Authorization')
            request['ha_authenticated']=auth in {'Bearer fixture-admin','Bearer fixture-user'}
            if request['ha_authenticated']:
                request['hass_user']=SimpleNamespace(is_admin=auth=='Bearer fixture-admin',id='synthetic-user')
            return await handler(request)
        app=web.Application(middlewares=[authenticate]);view.register(self.hass,app,app.router)
        client=TestClient(TestServer(app));await client.start_server();self.clients.append(client)
        raw=p.sign(payload(now=time.time()),SECRET)
        response=await client.post(o.ENDPOINT,data=raw,headers={'Authorization':'Bearer fixture-user'})
        self.assertEqual(response.status,403)
        response=await client.post(o.ENDPOINT,data=raw,headers={'Authorization':'Bearer fixture-admin'})
        self.assertEqual(response.status,200);self.assertLess(len(await response.read()),1024)
        response=await client.post(o.ENDPOINT,data=raw,headers={'Authorization':'Bearer fixture-admin'})
        self.assertEqual(response.status,400)
        response=await client.post(o.ENDPOINT,data=b'x'*(p.MAX_BYTES+1),headers={'Authorization':'Bearer fixture-admin'})
        self.assertEqual(response.status,400)
        response=await client.get(o.ENDPOINT,headers={'Authorization':'Bearer fixture-admin'})
        self.assertEqual(response.status,405)
        self.assertEqual(coordinator.receiver.value['sequence'],1)
        self.assertFalse(self.hass.services.has_service('hi_lab_controller','prepare_version'))

    @unittest.skipUnless(os.environ.get('HILC_CONTROLLER_SOURCE'), 'cross-repository interoperability requires explicit controller source')
    async def test_real_controller_publisher_through_ha_view_storage_and_signed_ack(self):
        await self._assert_controller_publisher(frontend=False)

    @unittest.skipUnless(os.environ.get('HILC_CONTROLLER_SOURCE'), 'cross-repository interoperability requires explicit controller source')
    async def test_frontend_controller_projection_through_ha_view_storage_and_signed_ack(self):
        await self._assert_controller_publisher(frontend=True)

    async def _assert_controller_publisher(self, *, frontend):
        root=Path(os.environ['HILC_CONTROLLER_SOURCE']).resolve()
        sys.path[:0]=[str(root),str(root/'src'),str(root/'tests')]
        from hi_lab_controller import integration_observation_publisher_v2 as publisher
        from hi_lab_controller.integration_observation_service_v1 import ObservationService
        from test_integration_observation_v1 import MemoryStore,Registry,healthy,request
        from test_integration_observation_publisher_v2 import FakeRegistry
        from tools.provision_observation_reporting import provision_absent
        local=Path(__file__).resolve().parents[1]/'custom_components/hi_lab_controller/observation_protocol.py'
        self.assertEqual(local.read_bytes(),(root/'src/hi_lab_controller/integration_observation_report_v2.py').read_bytes())
        coordinator=await self.pair()
        self.hass.data[o.RUNTIME_DATA]={'synthetic':SimpleNamespace(observation=coordinator)}
        @web.middleware
        async def authenticate(request,handler):
            request['ha_authenticated']=request.headers.get('Authorization')=='Bearer synthetic-test-token'
            if request['ha_authenticated']:request['hass_user']=SimpleNamespace(is_admin=True,id='synthetic-user')
            return await handler(request)
        app=web.Application(middlewares=[authenticate]);o.ObservationView(self.hass).register(self.hass,app,app.router)
        client=TestClient(TestServer(app));await client.start_server();self.clients.append(client)
        registry=FakeRegistry(str(client.make_url('')).rstrip('/'))
        directory=self.root/'publisher'
        provision_absent(directory,registry,{'controller_instance_id':INSTANCE,'stream_epoch':EPOCH,'secret':SECRET})
        custody=publisher.Custody(directory,registry)
        producer=publisher.Publisher(custody,publisher.Transport(registry));self.addCleanup(producer.close)
        model_registry=Registry()
        if frontend:
            from test_frontend_observation_v1 import frontend as frontend_profile
            model_registry.items=[frontend_profile()]
        selected=model_registry.profiles()[0]
        service=ObservationService(MemoryStore(),model_registry,healthy);self.addCleanup(service.close)
        service.handle_request(request('readiness',profile_id=selected['profile_id']))
        while service.future is not None:
            service.tick();await asyncio.sleep(.001)
        producer.tick(service.reporting_snapshot)
        await asyncio.wrap_future(producer.future)
        self.assertEqual(coordinator.current()['feed'],'fresh')
        self.assertEqual(coordinator.receiver.value['sequence'],1)
        self.assertIsNone(coordinator.current()['document']['campaign'])
        self.assertEqual(coordinator.current()['document']['selected_profile']['domain'],selected['domain'])
        self.assertEqual(coordinator.current()['document']['selected_profile']['integration_label'],selected['label'])
        before=service.store.read()
        await coordinator.async_close()
        successor=await self.coordinator()
        self.assertEqual(successor.receiver.value['sequence'],1)
        self.assertIsNone(successor.current()['document'])
        self.assertEqual(service.store.read(),before)


if __name__=='__main__':unittest.main()
