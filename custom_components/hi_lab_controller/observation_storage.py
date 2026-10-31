"""Descriptor-relative private replay custody outside HA's legacy status store.

Writes admit the original namespace and record before mutation, use an exclusive
staged file in the held parent, fsync/rename/readback, and preserve interrupted
stages. No startup repair, foreign-path write or automatic sequence reset.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import stat
import uuid

from . import observation_protocol as p
from .observation_receiver import await_physical

SCHEMA = 'hilc.observation-receiver-custody.v2'


def signature(info, file=False):
    base = (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid)
    return base + ((info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns) if file else ())


class VerifiedStore:
    def __init__(self, hass, key):
        self.hass = hass
        self.key = key
        self.path = Path(hass.config.path('.hi_lab_controller', 'observation-v2', key + '.json'))
        self.pins = None
        self.file_pin = None
        self.last_record = None

    def _check_dirs(self, dirs, pins):
        parts = self.path.parent.parts
        for i, fd in enumerate(dirs):
            p.require(signature(os.fstat(fd)) == pins[i], 'CUSTODY_INVALID')
            if i:
                p.require(signature(os.stat(parts[i], dir_fd=dirs[i-1], follow_symlinks=False)) == pins[i], 'CUSTODY_INVALID')

    def _open(self, create=False):
        p.require(self.path.is_absolute(), 'CUSTODY_INVALID')
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK | os.O_DIRECTORY
        dirs = [os.open('/', flags)]
        pins = [signature(os.fstat(dirs[0]))]
        try:
            parts = self.path.parent.parts[1:]
            for i, part in enumerate(parts):
                try:
                    fd = os.open(part, flags, dir_fd=dirs[-1])
                except FileNotFoundError:
                    p.require(create and i >= len(parts)-2 and part in {'.hi_lab_controller','observation-v2'}, 'CUSTODY_MISSING')
                    os.mkdir(part, 0o700, dir_fd=dirs[-1]);os.fsync(dirs[-1])
                    fd = os.open(part, flags, dir_fd=dirs[-1])
                dirs.append(fd);info = os.fstat(fd)
                p.require(info.st_uid in {0,os.geteuid()} and not stat.S_IMODE(info.st_mode) & 0o022, 'CUSTODY_INVALID')
                if i >= len(parts)-2:
                    p.require(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700, 'CUSTODY_INVALID')
                pins.append(signature(info))
            self._check_dirs(dirs,pins)
            if self.pins is not None:
                p.require(pins == self.pins, 'CUSTODY_REPLACED')
            else:
                self.pins = pins
            return dirs
        except BaseException:
            for fd in reversed(dirs):os.close(fd)
            raise

    def _read_at(self, fd):
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        handle = os.open(self.path.name, flags, dir_fd=fd)
        try:
            info = os.fstat(handle)
            p.require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                      and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
                      and 0 < info.st_size <= 65536, 'CUSTODY_INVALID')
            raw = os.read(handle, 65537)
            p.require(len(raw) == info.st_size and signature(os.fstat(handle),True) == signature(info,True), 'CUSTODY_INVALID')
            value = json.loads(raw)
            p.closed(value, {'schema_version','data'})
            p.require(value['schema_version'] == SCHEMA and p.canonical(value) == raw, 'CUSTODY_INVALID')
            pin = signature(info,True)
            p.require(signature(os.stat(self.path.name,dir_fd=fd,follow_symlinks=False),True) == pin, 'CUSTODY_INVALID')
            if self.file_pin is not None:p.require(self.file_pin == pin, 'CUSTODY_REPLACED')
            return value['data'],pin
        finally:os.close(handle)

    def _read(self):
        dirs = []
        try:
            dirs = self._open()
            record,pin = self._read_at(dirs[-1])
            self._check_dirs(dirs,self.pins)
            self.file_pin=pin;self.last_record=deepcopy(record)
            return record
        except FileNotFoundError:return None
        except p.Invalid as exc:
            if str(exc)=='CUSTODY_MISSING' and self.file_pin is None:return None
            raise
        except (OSError,ValueError,TypeError,RecursionError):raise p.Invalid('CUSTODY_INVALID') from None
        finally:
            for fd in reversed(dirs):os.close(fd)

    def _write(self, record, initialize=False):
        dirs=[];stage_fd=None
        try:
            dirs=self._open(create=initialize)
            fd=dirs[-1]
            if initialize:
                p.require(self.file_pin is None,'CUSTODY_EXISTS')
                try:os.stat(self.path.name,dir_fd=fd,follow_symlinks=False)
                except FileNotFoundError:pass
                else:raise p.Invalid('CUSTODY_EXISTS')
            else:
                p.require(self.file_pin is not None,'CUSTODY_MISSING')
                old,pin=self._read_at(fd)
                p.require(old==self.last_record and pin==self.file_pin,'CUSTODY_REPLACED')
            self._check_dirs(dirs,self.pins)
            raw=p.canonical({'schema_version':SCHEMA,'data':record})
            p.require(0<len(raw)<=65536,'CUSTODY_INVALID')
            stage='.pending-'+str(uuid.uuid4())
            stage_fd=os.open(stage,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=fd)
            offset=0
            while offset<len(raw):
                written=os.write(stage_fd,raw[offset:]);p.require(written>0,'CUSTODY_WRITE_FAILED');offset+=written
            os.fsync(stage_fd)
            self._check_dirs(dirs,self.pins)
            if not initialize:self._read_at(fd)
            stage_info=os.fstat(stage_fd)
            p.require(stat.S_ISREG(stage_info.st_mode) and stage_info.st_nlink==1
                      and stage_info.st_uid==os.geteuid() and stat.S_IMODE(stage_info.st_mode)==0o600
                      and signature(os.stat(stage,dir_fd=fd,follow_symlinks=False),True)==signature(stage_info,True),
                      'CUSTODY_REPLACED')
            # Initialization is no-clobber even against concurrent pairing attempts.
            if initialize:
                os.link(stage,self.path.name,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)
                os.unlink(stage,dir_fd=fd)
            else:os.rename(stage,self.path.name,src_dir_fd=fd,dst_dir_fd=fd)
            os.fsync(fd)
            expected=signature(os.fstat(stage_fd),True)
            p.require(expected[0:2] == signature(os.stat(self.path.name,dir_fd=fd,follow_symlinks=False),True)[0:2],'CUSTODY_INVALID')
            # Adopt only the inode just created by this exact write.
            self.file_pin=expected
            actual,pin=self._read_at(fd)
            p.require(actual==record and pin==expected,'CUSTODY_WRITE_FAILED')
            self._check_dirs(dirs,self.pins)
            self.last_record=deepcopy(record)
        except (OSError,ValueError,TypeError,RecursionError):
            raise p.Invalid('CUSTODY_WRITE_FAILED') from None
        finally:
            if stage_fd is not None:os.close(stage_fd)
            for fd in reversed(dirs):os.close(fd)

    async def async_load(self):
        return await self.hass.async_add_executor_job(self._read)

    async def async_save(self, record):
        p.require(not self.hass.is_stopping,'CUSTODY_WRITE_FAILED')
        await await_physical(self.hass.async_add_executor_job(self._write,record))
        p.require(not self.hass.is_stopping,'CUSTODY_WRITE_FAILED')

    async def initialize(self, record):
        p.require(not self.hass.is_stopping,'CUSTODY_WRITE_FAILED')
        await await_physical(self.hass.async_add_executor_job(self._write,record,True))
