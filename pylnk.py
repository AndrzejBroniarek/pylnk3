#!/usr/bin/python
#
# Python library for reading and writing Windows shortcut files (.lnk)
# Copyright 2011 Tim-Christian Mundt
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see
# <http://www.gnu.org/licenses/>.

import sys, os, time, re
from struct import pack, unpack
from pprint import pformat
from datetime import datetime
from StringIO import StringIO

#---- constants

_SIGNATURE = 'L\x00\x00\x00'
_GUID = '\x01\x14\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00F'
_LINK_INFO_HEADER_DEFAULT = 0x1C
_LINK_INFO_HEADER_OPTIONAL = 0x24

_LINK_FLAGS = ('has_shell_item_id_list', 'has_link_info', 'has_description',
              'has_relative_path', 'has_work_directory', 'has_arguments',
              'has_icon', 'is_unicode', 'force_no_link_info')

_FILE_ATTRIBUTES_FLAGS = ('read_only', 'hidden', 'system_file', 'reserved1',
                         'directory', 'archive', 'reserved2', 'normal',
                         'temporary', 'sparse_file', 'reparse_point',
                         'compressed', 'offline', 'not_content_indexed',
                         'encrypted')

_MODIFIER_KEYS = ('SHIFT', 'CONTROL', 'ALT')

WINDOW_NORMAL = "Normal"
WINDOW_MAXIMIZED = "Maximized"
WINDOW_MINIMIZED = "Minimized"
_SHOW_COMMANDS = {1:WINDOW_NORMAL, 3:WINDOW_MAXIMIZED, 7:WINDOW_MINIMIZED}
_SHOW_COMMAND_IDS = dict((v, k) for k, v in _SHOW_COMMANDS.iteritems())

DRIVE_UNKNOWN = "Unknown"
DRIVE_NO_ROOT_DIR = "No root directory"
DRIVE_REMOVABLE = "Removable"
DRIVE_FIXED = "Fixed (Hard disk)"
DRIVE_REMOTE = "Remote (Network drive)"
DRIVE_CDROM = "CD-ROM"
DRIVE_RAMDISK = "Ram disk"
_DRIVE_TYPES = {0: DRIVE_UNKNOWN,
                1: DRIVE_NO_ROOT_DIR,
                2: DRIVE_REMOVABLE,
                3: DRIVE_FIXED,
                4: DRIVE_REMOTE,
                5: DRIVE_CDROM,
                6: DRIVE_RAMDISK}
_DRIVE_TYPE_IDS = dict((v, k) for k, v in _DRIVE_TYPES.iteritems())

_KEYS = {0x30: '0', 0x31: '1', 0x32: '2', 0x33: '3', 0x34: '4', 0x35: '5', 0x36: '6',
        0x37: '7', 0x38: '8', 0x39: '9', 0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D',
        0x45: 'E', 0x46: 'F', 0x47: 'G', 0x48: 'H', 0x49: 'I', 0x4A: 'J', 0x4B: 'K',
        0x4C: 'L', 0x4D: 'M', 0x4E: 'N', 0x4F: 'O', 0x50: 'P', 0x51: 'Q', 0x52: 'R',
        0x53: 'S', 0x54: 'T', 0x55: 'U', 0x56: 'V', 0x57: 'W', 0x58: 'X', 0x59: 'Y',
        0x5A: 'Z', 0x70: 'F1', 0x71: 'F2', 0x72: 'F3', 0x73: 'F4', 0x74: 'F5',
        0x75: 'F6', 0x76: 'F7', 0x77: 'F8', 0x78: 'F9', 0x79: 'F10', 0x7A: 'F11',
        0x7B: 'F12', 0x7C: 'F13', 0x7D: 'F14', 0x7E: 'F15', 0x7F: 'F16', 0x80: 'F17',
        0x81: 'F18', 0x82: 'F19', 0x83: 'F20', 0x84: 'F21', 0x85: 'F22', 0x86: 'F23',
        0x87: 'F24', 0x90: 'NUM LOCK', 0x91: 'SCROLL LOCK'}
_KEY_CODES = dict((v, k) for k, v in _KEYS.iteritems())

ROOT_MY_COMPUTER = 'MY_COMPUTER'
ROOT_MY_DOCUMENTS = 'MY_DOCUMENTS'
ROOT_NETWORK_SHARE = 'NETWORK_SHARE'
ROOT_NETWORK_SERVER = 'NETWORK_SERVER'
ROOT_NETWORK_PLACES = 'NETWORK_PLACES'
ROOT_NETWORK_DOMAIN = 'NETWORK_DOMAIN'
ROOT_INTERNET = 'INTERNET'
ROOT_RECYLCE_BIN = 'RECYLCE_BIN'
ROOT_CONTROL_PANEL = 'CONTROL_PANEL'

_ROOT_LOCATIONS = {'{20D04FE0-3AEA-1069-A2D8-08002B30309D}': ROOT_MY_COMPUTER,
                  '{450D8FBA-AD25-11D0-98A8-0800361B1103}': ROOT_MY_DOCUMENTS,
                  '{54a754c0-4bf1-11d1-83ee-00a0c90dc849}': ROOT_NETWORK_SHARE,
                  '{c0542a90-4bf0-11d1-83ee-00a0c90dc849}': ROOT_NETWORK_SERVER,
                  '{208D2C60-3AEA-1069-A2D7-08002B30309D}': ROOT_NETWORK_PLACES,
                  '{46e06680-4bf0-11d1-83ee-00a0c90dc849}': ROOT_NETWORK_DOMAIN,
                  '{871C5380-42A0-1069-A2EA-08002B30309D}': ROOT_INTERNET,
                  '{645FF040-5081-101B-9F08-00AA002F954E}': ROOT_RECYLCE_BIN,
                  '{21EC2020-3AEA-1069-A2DD-08002B30309D}': ROOT_CONTROL_PANEL}
_ROOT_LOCATION_GUIDS = dict((v, k) for k, v in _ROOT_LOCATIONS.iteritems())

TYPE_FOLDER = 'FOLDER'
TYPE_FILE = 'FILE'
_ENTRY_TYPES = {0x31: 'FOLDER', 0x32: 'FILE',
               0x35: 'FOLDER (UNICODE)', 0x36: 'FILE (UNICODE)'}
_ENTRY_TYPE_IDS = dict((v, k) for k, v in _ENTRY_TYPES.iteritems())

_DRIVE_PATTERN = re.compile("(\w)[:/\\\\]*$")

#---- read and write binary data

def read_byte(buf):
    return unpack('<B', buf.read(1))[0]

def read_short(buf):
    return unpack('<H', buf.read(2))[0]

def read_int(buf):
    return unpack('<I', buf.read(4))[0]

def read_double(buf):
    return unpack('<Q', buf.read(8))[0]

def read_cunicode(buf):
    s = ""
    b = buf.read(2)
    while b!= '\x00\x00':
        s += b
        b = buf.read(2)
    return s.decode('utf-16-le')

def read_cstring(buf, padding=False):
    s = ""
    b = buf.read(1)
    while b != '\x00':
        s += b
        b = buf.read(1)
    if padding and not len(s) % 2:
        buf.read(1) # make length + terminator even
    #TODO: encoding is not clear, unicode-escape has been necessary sometimes
    return s.decode('cp1252')

def read_sized_string(buf, unicode=True):
    size = read_short(buf)
    if unicode:
        return buf.read(size*2).decode('utf-16-le')
    else:
        return buf.read(size)

def get_bits(value, start, count, length=16):
    mask = 0
    for i in range(count):
        mask = mask | 1 << i
    shift = length - start - count
    return value >> shift & mask

def read_dos_datetime(buf):
    date = read_short(buf)
    time = read_short(buf)
    year = get_bits(date, 0, 7) + 1980
    month = get_bits(date, 7, 4)
    day = get_bits(date, 11, 5)
    hour = get_bits(time, 0, 5)
    minute = get_bits(time, 5, 6)
    second = get_bits(time, 11, 5)
    return datetime(year, month, day, hour, minute, second)

def write_byte(val, buf):
    buf.write(pack('<B', val))

def write_short(val, buf):
    buf.write(pack('<H', val))

def write_int(val, buf):
    buf.write(pack('<I', val))

def write_double(val, buf):
    buf.write(pack('<Q', val))

def write_cstring(val, buf, padding=False):
    #val = val.encode('unicode-escape').replace('\\\\', '\\')
    val = val.encode('cp1252')
    buf.write(val + '\x00')
    if padding and not len(val) % 2:
        buf.write('\x00')

def write_cunicode(val, buf):
    uni = val.encode('utf-16-le')
    buf.write(uni + '\x00\x00')

def write_sized_string(val, buf, unicode=True):
    size = len(val)
    write_short(size, buf)
    if unicode:
        buf.write(val.encode('utf-16-le'))
    else:
        buf.write(val)

def put_bits(bits, target, start, count, length=16):
    return target | bits << (length - start - count)

def write_dos_datetime(val, buf):
    date = time = 0
    date = put_bits(val.year-1980, date, 0, 7)
    date = put_bits(val.month, date, 7, 4)
    date = put_bits(val.day, date, 11, 5)
    time = put_bits(val.hour, time, 0, 5)
    time = put_bits(val.minute, time, 5, 6)
    time = put_bits(val.second, time, 11, 5)
    write_short(date, buf)
    write_short(time, buf)

#---- helpers

def convert_time_to_unix(windows_time):
    # Windows time is specified as the number of 0.1 nanoseconds since January 1, 1601.
    # UNIX time is specified as the number of seconds since January 1, 1970.
    # There are 134774 days (or 11644473600 seconds) between these dates.
    unix_time = windows_time / 10000000.0 - 11644473600
    return datetime.fromtimestamp(unix_time)

def convert_time_to_windows(unix_time):
    if isinstance(unix_time, datetime):
        unix_time = time.mktime(unix_time.timetuple())
    return long((unix_time + 11644473600) * 10000000)

class FormatException(Exception):
    pass

class MissingInformationException(Exception):
    pass

class InvalidKeyException(Exception):
    pass

def assert_lnk_signature(f):
    f.seek(0)
    sig = f.read(4)
    guid = f.read(16)
    if sig != _SIGNATURE:
        raise FormatException("This is not a .lnk file.")
    if guid != _GUID:
        raise FormatException("Cannot read this kind of .lnk file.")

def is_lnk(f):
    if hasattr(f, 'name'):
        if f.name.split(os.path.extsep)[-1] == "lnk":
            assert_lnk_signature(f)
            return True
        else:
            return False
    else:
        try:
            assert_lnk_signature(f)
            return True
        except FormatException:
            return False

def path_levels(p):
    dirname, base = os.path.split(p)
    if base != '':
        for level in path_levels(dirname):
            yield level
    yield p

def is_drive(data):
    if type(data) not in (str, unicode):
        return False
    p = re.compile("[a-zA-Z]:\\\\?$")
    return p.match(data) is not None

#---- data structures

class Flags(object):
    
    def __init__(self, flag_names, flags_bytes=0):
        self._flag_names = flag_names
        self._flags = dict([(name, None) for name in flag_names])
        self.set_flags(flags_bytes)
    
    def set_flags(self, flags_bytes):
        for pos in range(len(self._flag_names)):
            self._flags[self._flag_names[pos]] = flags_bytes >> pos & 0x1 and True or False
    
    def bytes(self):
        bytes = 0
        for pos in range(len(self._flag_names)):
            bytes = (self._flags[self._flag_names[pos]] and 1 or 0) << pos | bytes
        return bytes
    bytes = property(bytes)
    
    def __getitem__(self, key):
        return object.__getattribute__(self, '_flags')[key]
    
    def __setitem__(self, key, value):
        if not self._flags.has_key(key):
            raise KeyError("The key '%s' is not defined for those flags." % key)
        self._flags[key] = value
    
    def __getattr__(self, key):
        return object.__getattribute__(self, '_flags')[key]
    
    def __setattr__(self, key, value):
        if not self.__dict__.has_key('_flags'):
            object.__setattr__(self, key, value)
        elif self.__dict__.has_key(key):
            object.__setattr__(self, key, value)
        else:
            self.__setitem__(key, value)

    def __str__(self):
        return pformat(self._flags, indent=2)


class ModifierKeys(Flags):
    
    def __init__(self, flags_bytes=0):
        Flags.__init__(self, _MODIFIER_KEYS, flags_bytes)
    
    def __str__(self):
        s = ""
        s += self.CONTROL and "CONTROL+" or ""
        s += self.SHIFT and "SHIFT+" or ""
        s += self.ALT and "ALT+" or ""
        return s


class RootEntry(object):
    
    def __init__(self, root):
        if root is not None:
            if root in _ROOT_LOCATION_GUIDS.keys():
                self.root = root
                self.guid = _ROOT_LOCATION_GUIDS[root]
            else:
                bytes = root
                if len(bytes) == 18: # and bytes[:2] == '\x1F\x50':
                    # '\x1F\x50' for MY_COMPUTER
                    # '\x1FX' for NETWORK
                    bytes = bytes[2:]
                if len(bytes) != 16:
                    raise FormatException("This is no valid _GUID: %s" % bytes)
                ordered = [bytes[3], bytes[2], bytes[1], bytes[0], bytes[5], bytes[4],
                           bytes[7], bytes[6], bytes[8], bytes[9], bytes[10], bytes[11],
                           bytes[12], bytes[13], bytes[14], bytes[15]]
                self.guid = "{%02X%02X%02X%02X-%02X%02X-%02X%02X-%02X%02X-%02X%02X%02X%02X%02X%02X}" % tuple(
                       [ord(x) for x in ordered])
                self.root = _ROOT_LOCATIONS.get(self.guid, "UNKNOWN")

    def bytes(self):
        guid = self.guid[1:-1].replace('-', '')
        chars = [chr(int(x, 16)) for x in [guid[i:i+2] for i in range(0, 32, 2)]]
        return '\x1F\x50' + chars[3] + chars[2] + chars[1] + chars[0] + chars[5] + chars[4] \
               + chars[7] + chars[6] + ''.join(chars[8:])
    bytes = property(bytes)
    
    def __str__(self):
        return "<RootEntry: %s>" % self.root


class DriveEntry(object):
    
    def __init__(self, drive):
        if len(drive) == 23:
            self.drive = drive[1:3]
        else:
            m = _DRIVE_PATTERN.match(drive.strip())
            if m:
                self.drive = m.groups()[0].upper() + ':'
            else:
                raise FormatException("This is not a valid drive: " + drive)
    
    def bytes(self):
        return '/' + self.drive + '\\' + '\x00' * 19
    bytes = property(bytes)
    
    def __str__(self):
        return "<DriveEntry: %s>" % self.drive


class PathSegmentEntry(object):
    
    def __init__(self, bytes=None):
        self.type = None
        self.file_size = None
        self.modified = None
        self.short_name = None
        self.created = None
        self.accessed = None
        self.full_name = None
        if bytes is not None:
            buf = StringIO(bytes)
            self.type = _ENTRY_TYPES.get(read_short(buf), 'UNKNOWN')
            short_name_is_unicode = self.type.endswith('(UNICODE)')
            self.file_size = read_int(buf)
            self.modified = read_dos_datetime(buf)
            unknown = read_short(buf) # should be 0x10
            if short_name_is_unicode:
                self.short_name = read_cunicode(buf)
            else:
                self.short_name = read_cstring(buf, padding=True)
            indicator_1 = read_short(buf) # see below
            only_83 = read_short(buf) < 0x03
            unknown = read_short(buf) # 0x04
            self.is_unicode = read_short(buf) == 0xBeef
            self.created = read_dos_datetime(buf)
            self.accessed = read_dos_datetime(buf)
            offset_unicode = read_short(buf)
            only_83_2 = offset_unicode >= indicator_1 or offset_unicode < 0x14
            offset_ansi = read_short(buf)
            self.full_name = read_cunicode(buf)
            offset_part2 = read_short(buf) # offset to byte after short name
    
    def create_for_path(cls, path):
        entry = cls()
        entry.type = os.path.isdir(path) and TYPE_FOLDER or TYPE_FILE
        st = os.stat(path)
        entry.file_size = st.st_size
        entry.modified = datetime.fromtimestamp(st.st_mtime)
        entry.short_name = os.path.split(path)[1]
        entry.created = datetime.fromtimestamp(st.st_ctime)
        entry.accessed = datetime.fromtimestamp(st.st_atime)
        entry.full_name = entry.short_name
        return entry
    create_for_path = classmethod(create_for_path)
    
    def _validate(self):
        if self.type is None:
            raise MissingInformationException("Type is missing, choose either TYPE_FOLDER or TYPE_FILE.")
        if self.file_size is None:
            if self.type.startswith('FOLDER'):
                self.file_size = 0
            else:
                raise MissingInformationException("File size missing")
        if self.modified is None or self.accessed is None or self.created is None:
            raise MissingInformationException("Date information missing")
        if self.full_name is None:
            raise MissingInformationException("A full name is missing")
        if self.short_name is None:
            self.short_name = self.full_name
    
    def bytes(self):
        self._validate()
        out = StringIO()
        entry_type = self.type
        short_name_len = len(self.short_name) + 1
        try:
            self.short_name.decode("ascii")
            short_name_is_unicode = False
            short_name_len += short_name_len % 2 # padding
        except (UnicodeEncodeError, UnicodeDecodeError):
            short_name_is_unicode = True
            short_name_len = short_name_len * 2
            self.type += " (UNICODE)"
        write_short(_ENTRY_TYPE_IDS[entry_type], out)
        write_int(self.file_size, out)
        write_dos_datetime(self.modified, out)
        write_short(0x10, out)
        if short_name_is_unicode:
            write_cunicode(self.short_name, out)
        else:
            write_cstring(self.short_name, out, padding=True)
        indicator = 24 + 2 * len(self.short_name)
        write_short(indicator, out)
        write_short(0x03, out)
        write_short(0x04, out)
        write_short(0xBeef, out)
        write_dos_datetime(self.created, out)
        write_dos_datetime(self.accessed, out)
        offset_unicode = 0x14 # fixed data structure, always the same
        write_short(offset_unicode, out)
        offset_ansi = 0 # we always write unicode
        write_short(offset_ansi, out)
        write_cunicode(self.full_name, out)
        offset_part2 = 0x0E + short_name_len
        write_short(offset_part2, out)
        return out.getvalue()
    bytes = property(bytes)
    
    def __str__(self):
        return "<PathSegmentEntry: %s>" % self.full_name


class LinkTargetIDList(object):
    
    def __init__(self, bytes=None):
        self.items = []
        if bytes is not None:
            buf = StringIO(bytes)
            raw = []
            entry_len = read_short(buf)
            while entry_len > 0:
                raw.append(buf.read(entry_len - 2)) # the length includes the size
                entry_len = read_short(buf)
            self._interpret(raw)
    
    def _interpret(self, raw):
        if len(raw[0]) == 0x12:
            self.items.append(RootEntry(raw[0]))
            if self.items[0].root == ROOT_MY_COMPUTER:
                if not len(raw[1]) == 0x17:
                    raise ValueError("This seems to be an absolute link which requires a drive as second element.")
                self.items.append(DriveEntry(raw[1]))
                items = raw[2:]
            elif self.items[0].root == ROOT_NETWORK_PLACES:
                raise NotImplementedError("""Parsing network lnks has not yet been implemented.
                     If you need it just contact me and we'll see...""")
            else:
                items = raw[1:]
        else:
            items = raw
        for item in items:
            self.items.append(PathSegmentEntry(item))
    
    def get_path(self):
        segments = []
        for item in self.items:
            if type(item) == RootEntry:
                segments.append('%' + item.root + '%')
            elif type(item) == DriveEntry:
                segments.append(item.drive)
            elif type(item) == PathSegmentEntry:
                segments.append(item.full_name)
            else:
                segments.append(item)
        return '\\'.join(segments)
    
    def _validate(self):
        if type(self.items[0]) == RootEntry:
            if self.items[0].root == ROOT_MY_COMPUTER \
            and type(self.items[1]) != DriveEntry:
                raise ValueError("A drive is required for absolute lnks")
    
    def bytes(self):
        self._validate()
        out = StringIO()
        for item in self.items:
            bytes = item.bytes
            write_short(len(bytes) + 2, out) # len + terminator
            out.write(bytes)
        out.write('\x00\x00')
        return out.getvalue()
    bytes = property(bytes)
    
    def __str__(self):
        return "<LinkTargetIDList:\n%s>" % pformat([str(item) for item in self.items])


class LinkInfo(object):

    def __init__(self, lnk=None):
        if lnk is not None:
            self.start = lnk.tell()
            self.size = read_int(lnk)
            self.header_size = read_int(lnk)
            link_info_flags = read_int(lnk)
            self.local = link_info_flags & 1
            self.remote = link_info_flags & 2
            self.offs_local_volume_table = read_int(lnk)
            self.offs_local_base_path = read_int(lnk)
            self.offs_network_volume_table = read_int(lnk)
            self.offs_base_name = read_int(lnk)
            if self.header_size >= _LINK_INFO_HEADER_OPTIONAL:
                print "TODO: read the unicode stuff" # TODO: read the unicode stuff
            self._parse_path_elements(lnk)
        else:
            self.size = None
            self.header_size = _LINK_INFO_HEADER_DEFAULT
            self.remote = None
            self.offs_local_volume_table = 0
            self.offs_local_base_path = 0
            self.offs_network_volume_table = 0
            self.offs_base_name = 0
            self.drive_type = None
            self.drive_serial = None
            self.volume_label = None
            self.local_base_path = None
            self.network_share_name = None
            self.base_name = None
            self._path = None

    def _parse_path_elements(self, lnk):
        if self.remote:
            # 20 is the offset of the network share name
            lnk.seek(self.start + self.offs_network_volume_table + 20)
            self.network_share_name = read_cstring(lnk)
            lnk.seek(self.start + self.offs_base_name)
            self.base_name = read_cstring(lnk)
        if self.local:
            lnk.seek(self.start + self.offs_local_volume_table + 4)
            self.drive_type = _DRIVE_TYPES.get(read_int(lnk))
            self.drive_serial = read_int(lnk)
            lnk.read(4) # volume name offset (10h)
            self.volume_label = read_cstring(lnk)
            lnk.seek(self.start + self.offs_local_base_path)
            self.local_base_path = read_cstring(lnk)
            # TODO: unicode
        self.make_path()

    def make_path(self):
        if self.remote:
            self._path = self.network_share_name + self.base_name
        if self.local:
            self._path = self.local_base_path
    
    def write(self, lnk):
        if self.remote is None:
            raise MissingInformationException("No location information given.")
        self.start = lnk.tell()
        self._calculate_sizes_and_offsets()
        write_int(self.size, lnk)
        write_int(self.header_size, lnk)
        write_int((self.local and 1) + (self.remote and 2), lnk)
        write_int(self.offs_local_volume_table, lnk)
        write_int(self.offs_local_base_path, lnk)
        write_int(self.offs_network_volume_table, lnk)
        write_int(self.offs_base_name, lnk)
        if self.remote:
            self._write_network_volume_table(lnk)
            write_cstring(self.base_name, lnk)
        else:
            self._write_local_volume_table(lnk)
            write_cstring(self.local_base_path, lnk, padding=True)
    
    def _calculate_sizes_and_offsets(self):
        self.size_base_name = 1 # len(self.base_name) + 1 # zero terminated strings
        self.size = 28 + self.size_base_name
        if self.remote:
            self.size_network_volume_table = 20 + len(self.network_share_name) + 1
            self.size += self.size_network_volume_table
            self.offs_local_volume_table = 0
            self.offs_local_base_path = 0
            self.offs_network_volume_table = 28
            self.offs_base_name = self.offs_network_volume_table + self.size_network_volume_table
        else:
            self.size_local_volume_table = 16 + len(self.volume_label) + 1
            self.size_local_base_path = len(self.local_base_path) + 1
            self.size += self.size_local_volume_table + self.size_local_base_path
            self.offs_local_volume_table = 28
            self.offs_local_base_path = self.offs_local_volume_table + self.size_local_volume_table
            self.offs_network_volume_table = 0
            self.offs_base_name = self.offs_local_base_path + self.size_local_base_path
    
    def _write_network_volume_table(self, buf):
        write_int(self.size_network_volume_table, buf)
        write_int(2, buf) # ?
        write_int(20, buf) # size of Network Volume Table
        write_int(0, buf) # ?
        write_int(131072, buf) # ?
        write_cstring(self.network_share_name, buf)
    
    def _write_local_volume_table(self, buf):
        write_int(self.size_local_volume_table, buf)
        try:
            drive_type = _DRIVE_TYPE_IDS[self.drive_type]
        except KeyError:
            raise ValueError("This is not a valid drive type: %s" % self.drive_type)
        write_int(drive_type, buf)
        write_int(self.drive_serial, buf)
        write_int(16, buf) # volume name offset
        write_cstring(self.volume_label, buf)
    
    def _get_path(self):
        return self._path
    path = property(_get_path)

    def __str__(self):
        s = "File Location Info:"
        if self._path is None:
            return s + " <not specified>"
        if self.remote:
            s += "\n  (remote)"
            s += "\n  Network Share: %s" % self.network_share_name
            s += "\n  Base Name: %s" % self.base_name
        else:
            s += "\n  (local)"
            s += "\n  Volume Type: %s" % self.drive_type
            s += "\n  Volume Serial Number: %s" % self.drive_serial
            s += "\n  Volume Label: %s" % self.volume_label
            s += "\n  Path: %s" % self.local_base_path
        return s


class Lnk(object):
    
    def __init__(self, f=None):
        self.file = None
        if type(f) == str or type(f) == unicode:
            self.file = f
            try:
                f = open(self.file, 'rb')
            except IOError:
                self.file += ".lnk"
                f = open(self.file, 'rb')
        # defaults
        self.link_flags = Flags(_LINK_FLAGS)
        self.file_flags = Flags(_FILE_ATTRIBUTES_FLAGS)
        self.creation_time = datetime.now()
        self.access_time = datetime.now()
        self.modification_time = datetime.now()
        self.file_size = 0
        self.icon_index = 0
        self._show_command = WINDOW_NORMAL
        self.hot_key = None
        self._link_info = LinkInfo()
        self.description = None
        self.relative_path = None
        self.work_dir = None
        self.arguments = None
        self.icon = None
        if f is not None:
            assert_lnk_signature(f)
            self._parse_lnk_file(f)
        if self.file:
            f.close()
    
    def _read_hot_key(self, lnk):
        low = read_byte(lnk)
        high = read_byte(lnk)
        key = _KEYS.get(low, '')
        modifier = high and str(ModifierKeys(high)) or ''
        return modifier + key
    
    def _write_hot_key(self, hot_key, lnk):
        if hot_key is None:
            low = high = 0
        else:
            hot_key = hot_key.split('+')
            try:
                low = _KEY_CODES[hot_key[-1]]
            except KeyError:
                raise InvalidKeyException("Cannot find key code for %s" % hot_key[1])
            modifiers = ModifierKeys()
            for modifier in hot_key[:-1]:
                modifiers[modifier.upper()] = True
            high = modifiers.bytes
        write_byte(low, lnk)
        write_byte(high, lnk)

    def _parse_lnk_file(self, lnk):
        lnk.seek(20) # after signature and guid
        self.link_flags.set_flags(read_int(lnk))
        self.file_flags.set_flags(read_int(lnk))
        self.creation_time = convert_time_to_unix(read_double(lnk))
        self.access_time = convert_time_to_unix(read_double(lnk))
        self.modification_time = convert_time_to_unix(read_double(lnk))
        self.file_size = read_int(lnk)
        self.icon_index = read_int(lnk)
        self._show_command = _SHOW_COMMANDS[read_int(lnk)]
        self.hot_key = self._read_hot_key(lnk)
        lnk.read(10) # reserved (0)
        if self.link_flags.has_shell_item_id_list:
            shell_item_id_list_size = read_short(lnk)
            self.shell_item_id_list = LinkTargetIDList(lnk.read(shell_item_id_list_size))
        if self.link_flags.has_link_info and not self.link_flags.force_no_link_info:
            self._link_info = LinkInfo(lnk)
            lnk.seek(self._link_info.start + self._link_info.size)
        if self.link_flags.has_description:
            self.description = read_sized_string(lnk, self.link_flags.is_unicode)
        if self.link_flags.has_relative_path:
            self.relative_path = read_sized_string(lnk, self.link_flags.is_unicode)
        if self.link_flags.has_work_directory:
            self.work_dir = read_sized_string(lnk, self.link_flags.is_unicode)
        if self.link_flags.has_arguments:
            self.arguments = read_sized_string(lnk, self.link_flags.is_unicode)
        if self.link_flags.has_icon:
            self.icon = read_sized_string(lnk, self.link_flags.is_unicode)
    
    def save(self, f=None, force_ext=False):
        if f is None:
            f = self.file
        if f is None:
            raise ValueError("File (name) missing for saveing the lnk")
        is_file = hasattr(f, 'write')
        if not is_file:
            if not type(f) == str and not type(f) == unicode:
                raise ValueError("Need a writeable object or a file name to save to, got %s" % f)
            if force_ext:
                if not f.lower().endswith('.lnk'):
                    f += '.lnk'
            f = open(f, 'wb')
        self.write(f)
        # only close the stream if it's our own
        if not is_file:
            f.close()
    
    def write(self, lnk):
        lnk.write(_SIGNATURE)
        lnk.write(_GUID)
        write_int(self.link_flags.bytes, lnk)
        write_int(self.file_flags.bytes, lnk)
        write_double(convert_time_to_windows(self.creation_time), lnk)
        write_double(convert_time_to_windows(self.access_time), lnk)
        write_double(convert_time_to_windows(self.modification_time), lnk)
        write_int(self.file_size, lnk)
        write_int(self.icon_index, lnk)
        write_int(_SHOW_COMMAND_IDS[self._show_command], lnk)
        self._write_hot_key(self.hot_key, lnk)
        lnk.write('\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00') # reserved
        if self.link_flags.has_shell_item_id_list:
            siil = self.shell_item_id_list.bytes
            write_short(len(siil), lnk)
            lnk.write(siil)
        if self.link_flags.has_link_info:
            self._link_info.write(lnk)
        if self.link_flags.has_description:
            write_sized_string(self.description, lnk, self.link_flags.is_unicode)
        if self.link_flags.has_relative_path:
            write_sized_string(self.relative_path, lnk, self.link_flags.is_unicode)
        if self.link_flags.has_work_directory:
            write_sized_string(self.work_dir, lnk, self.link_flags.is_unicode)
        if self.link_flags.has_arguments:
            write_sized_string(self.arguments, lnk, self.link_flags.is_unicode)
        if self.link_flags.has_icon:
            write_sized_string(self.icon, lnk, self.link_flags.is_unicode)
        lnk.write('\x00\x00\x00\x00') # header_size

    def _get_shell_item_id_list(self):
        return self._shell_item_id_list
    def _set_shell_item_id_list(self, shell_item_id_list):
        self._shell_item_id_list = shell_item_id_list
        self.link_flags.has_shell_item_id_list = shell_item_id_list != None
    shell_item_id_list = property(_get_shell_item_id_list, _set_shell_item_id_list)

    def _get_link_info(self):
        return self._link_info
    def _set_link_info(self, link_info):
        self._link_info = link_info
        self.link_flags.force_no_link_info = link_info == None
        self.link_flags.has_link_info = link_info != None
    link_info = property(_get_link_info, _set_link_info)

    def _get_description(self):
        return self._description
    def _set_description(self, description):
        self._description = description
        self.link_flags.has_description = description != None
    description = property(_get_description, _set_description)

    def _get_relative_path(self):
        return self._relative_path
    def _set_relative_path(self, relative_path):
        self._relative_path = relative_path
        self.link_flags.has_relative_path = relative_path != None
    relative_path = property(_get_relative_path, _set_relative_path)

    def _get_work_dir(self):
        return self._work_dir
    def _set_work_dir(self, work_dir):
        self._work_dir = work_dir
        self.link_flags.has_work_directory = work_dir != None
    work_dir = working_dir = property(_get_work_dir, _set_work_dir)

    def _get_arguments(self):
        return self._arguments
    def _set_arguments(self, arguments):
        self._arguments = arguments
        self.link_flags.has_arguments = arguments != None
    arguments = property(_get_arguments, _set_arguments)

    def _get_icon(self):
        return self._icon
    def _set_icon(self, icon):
        self._icon = icon
        self.link_flags.has_icon = icon != None
    icon = property(_get_icon, _set_icon)
    
    def _get_window_mode(self):
        return self._show_command
    def _set_window_mode(self, value):
        if not value in _SHOW_COMMANDS.values():
            raise ValueError("Not a valid window mode: %s. Choose any of pylnk.WINDOW_*" % value)
        self._show_command = value
    window_mode = show_command = property(_get_window_mode, _set_window_mode)

    def _get_path(self):
        return self._shell_item_id_list.get_path()
    path = property(_get_path)
    
    def specify_local_location(self, path, drive_type=None, drive_serial=None, volume_label=None):
        self._link_info.drive_type = drive_type or DRIVE_UNKNOWN
        self._link_info.drive_serial = drive_serial or ''
        self._link_info.volume_label = volume_label or ''
        self._link_info.local_base_path = path
        self._link_info.local = True
        self._link_info.make_path()
    
    def specify_remote_location(self, network_share_name, base_name):
        self._link_info.network_share_name = network_share_name
        self._link_info.base_name = base_name
        self._link_info.remote = True
        self._link_info.make_path()

    def __str__(self):
        s = "Target file:\n"
        s += str(self.file_flags)
        s += "\nCreation Time: %s" % self.creation_time
        s += "\nModification Time: %s" % self.modification_time
        s += "\nAccess Time: %s" % self.access_time
        s += "\nFile size: %s" % self.file_size
        s += "\nWindow mode: %s" % self._show_command
        s += "\nHotkey: %s\n" % self.hot_key
        s += str(self._link_info)
        if self.link_flags.has_shell_item_id_list:
            s += "\n%s" % self.shell_item_id_list
        if self.link_flags.has_description:
            s += "\nDescription: %s" % self.description
        if self.link_flags.has_relative_path:
            s += "\nRelative Path: %s" % self.relative_path
        if self.link_flags.has_work_directory:
            s += "\nWorking Directory: %s" % self.work_dir
        if self.link_flags.has_arguments:
            s += "\nCommandline Arguments: %s" % self.arguments
        if self.link_flags.has_icon:
            s += "\nIcon: %s" % self.icon
        s += "\nUsed Path: %s" % self.shell_item_id_list.get_path()
        return s

#---- convenience functions

def parse(lnk):
    return Lnk(lnk)

def create(f=None):
    lnk = Lnk()
    lnk.file = f
    return lnk

def for_file(target_file, lnk_name=None):
    lnk = create(lnk_name)
    lnk.link_info = None
    levels = list(path_levels(target_file))
    elements = [RootEntry(ROOT_MY_COMPUTER),
                DriveEntry(levels[0])]
    for level in levels[1:]:
        segment = PathSegmentEntry.create_for_path(level)
        elements.append(segment)
    lnk.shell_item_id_list = LinkTargetIDList()
    lnk.shell_item_id_list.items = elements
    if lnk_name:
        lnk.save()
    return lnk

def from_segment_list(data, lnk_name=None):
    """
    Creates a lnk file from a list of path segments.
    If lnk_name is given, the resulting lnk will be saved
    to a file with that name.
    The expected list for has the following format ("C:\\dir\\file.txt"):
    
    ['c:\\',
     {'type': TYPE_FOLDER,
      'size': 0,            # optional for folders
      'name': "dir",
      'created': datetime.datetime(2012, 10, 12, 23, 28, 11, 8476),
      'modified': datetime.datetime(2012, 10, 12, 23, 28, 11, 8476),
      'accessed': datetime.datetime(2012, 10, 12, 23, 28, 11, 8476)
     },
     {'type': TYPE_FILE,
      'size': 823,
      'name': "file.txt",
      'created': datetime.datetime(2012, 10, 12, 23, 28, 11, 8476),
      'modified': datetime.datetime(2012, 10, 12, 23, 28, 11, 8476),
      'accessed': datetime.datetime(2012, 10, 12, 23, 28, 11, 8476)
     }
    ]
    
    For relative paths just omit the drive entry.
    Hint: Correct dates really are not crucial for working lnks.
    """
    if type(data) not in (list, tuple):
        raise ValueError("Invalid data format, list or tuple expected")
    lnk = Lnk()
    entries = []
    if is_drive(data[0]):
        # this is an absolute link
        entries.append(RootEntry(ROOT_MY_COMPUTER))
        if not data[0].endswith('\\'):
            data[0] += "\\"
        drive = data.pop(0).encode("ascii")
        entries.append(DriveEntry(drive))
    for level in data:
        segment = PathSegmentEntry()
        segment.type = level['type']
        if level['type'] == TYPE_FOLDER:
            segment.file_size = 0
        else:
            segment.file_size = level['size']
        segment.short_name = level['name']
        segment.full_name = level['name']
        segment.created = level['created']
        segment.modified = level['modified']
        segment.accessed = level['accessed']
        entries.append(segment)
    lnk.shell_item_id_list = LinkTargetIDList()
    lnk.shell_item_id_list.items = entries
    if data[-1]['type'] == TYPE_FOLDER:
        lnk.file_flags.directory = True
    if lnk_name:
        lnk.save(lnk_name)
    return lnk

def get_prop(obj, prop_queue):
    attr = getattr(obj, prop_queue[0])
    if len(prop_queue) > 1:
        return get_prop(attr, prop_queue[1:])
    return attr

def usage_and_exit():
    usage = """usage: pylnk.py c[reate] TARGETFILE LNKFILE
       pylnk.py p[arse] LNKFILE [PROPERTY[, PROPERTY[, ...]]]"""
    print usage
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        usage_and_exit()
    if sys.argv[1] in ['h', '-h', '--help']:
        usage_and_exit()
    action = sys.argv[1]
    if not action in ['c', 'create', 'p', 'parse']:
        print "unknown action: " + action
        usage_and_exit()
    if action.startswith('c'):
        if len(sys.argv) < 4:
            usage_and_exit()
        for_file(sys.argv[2], sys.argv[3])
    elif action.startswith('p'):
        if len(sys.argv) < 3:
            usage_and_exit()
        lnk = parse(sys.argv[2])
        props = sys.argv[3:]
        if len(props) == 0:
            print str(lnk).decode('cp1252')
        else:
            for prop in props:
                print str(get_prop(lnk, prop.split('.'))).decode('cp1252')
