#!/usr/bin/env python3
"""Compare compiled AWDL virtual slots with the local Tahoe native driver.

Run after building AirportMtkWlan for x86_64/__MAC_26_0. This checks binary
slot/signature layout only; it does not validate native object lifetimes,
private argument semantics, packet ownership, or RF interoperability.
Only Python's standard library and Apple's nm are required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[2]
FAMILY_UUID = "4184F404-9547-3499-A311-C1920829EA25"
CORE_UUID = "D09C7323-1C09-36E3-B8C1-B58E52F48537"
LAST_NATIVE_SLOT = 0x11C0
VTABLE = "__ZTV23AirportMtkAwdlInterface"
NATIVE_VTABLE = "__ZTV30AppleBCMWLANProximityInterface"
ANCHORS = {
    0x5C0: "start", 0x5C8: "stop", 0x670: "attach", 0x678: "detach",
    0x8E8: "prepareBSDInterface", 0x910: "processBSDCommand",
    0x930: "setInterfaceEnable", 0x9E0: "bpfTap",
    0xA68: "getHardwareAddress", 0xBA8: "getController",
    0xC68: "findOrCreateFlowQueue", 0xC90: "cachePeer",
    0xCD0: "findPeer", 0xE68: "init", 0xE70: "setLinkState",
    0xF40: "setMacAddress", 0xFC8: "getSSID",
    0x1108: "setPEER_CACHE_CONTROL", 0x11C0: "getTX_RATE",
}


def commands(data, header=0):
    if struct.unpack_from("<I", data, header)[0] != 0xFEEDFACF:
        raise ValueError("Expected a little-endian 64-bit Mach-O header")
    cursor = header + 32
    for _ in range(struct.unpack_from("<I", data, header + 16)[0]):
        command, size = struct.unpack_from("<II", data, cursor)
        if size < 8 or cursor + size > len(data):
            raise ValueError("Invalid Mach-O load command")
        yield command, cursor, size
        cursor += size


def string_at(data, offset):
    return data[offset:data.index(b"\0", offset)].decode()


def compiled_slots(path):
    data = path.read_bytes()
    if struct.unpack_from("<I", data, 4)[0] != 0x01000007:
        raise ValueError("Expected an x86_64 AWDL object")
    sections = []
    symtab = None
    for command, cursor, _ in commands(data):
        if command == 0x19:  # LC_SEGMENT_64
            for i in range(struct.unpack_from("<I", data, cursor + 64)[0]):
                section = cursor + 72 + i * 80
                name, segment, address, size, offset, align, reloc, count, flags = \
                    struct.unpack_from("<16s16sQQIIIII", data, section)
                sections.append((address, size, reloc, count))
        elif command == 2:  # LC_SYMTAB
            symtab = struct.unpack_from("<IIII", data, cursor + 8)
    if not symtab:
        raise ValueError("Object has no symbol table")
    symoff, count, stroff, strsize = symtab
    symbols = []
    for i in range(count):
        index, kind, section, desc, value = struct.unpack_from("<IBBHQ", data, symoff + i * 16)
        symbols.append((string_at(data, stroff + index), value, kind))
    addresses = [value for name, value, kind in symbols if name == VTABLE and kind & 0xE]
    if len(addresses) != 1:
        raise ValueError("Expected exactly one compiled AWDL vtable")
    address = addresses[0]
    end = min(value for name, value, kind in symbols
              if kind & 0xE and value > address and name.startswith("__ZTV"))
    slots = {}
    for section_address, size, reloc, count in sections:
        for i in range(count):
            offset, bits = struct.unpack_from("<II", data, reloc + i * 8)
            target = section_address + offset
            if address + 16 <= target < end:
                # x86_64 relocation_info: external, 64-bit, UNSIGNED.
                if not (bits >> 27) & 1 or (bits >> 25) & 3 != 3 or bits >> 28 != 0:
                    raise ValueError("Unexpected AWDL vtable relocation")
                slots[target - address - 16] = symbols[bits & 0xFFFFFF][0]
    expected = set(range(0, LAST_NATIVE_SLOT + 8, 8))
    if set(slots) != expected:
        raise ValueError("AWDL table is missing slots or contains unexpected appended methods: "
                         f"missing={sorted(expected-set(slots))}, extra={sorted(set(slots)-expected)}")
    return slots


def native_slots(path, family_uuid, core_uuid):
    data = path.read_bytes()
    images = {}
    segments = []
    for command, cursor, _ in commands(data):
        if command != 0x80000035:  # LC_FILESET_ENTRY
            continue
        address, header, nameoffset, reserved = struct.unpack_from("<QQII", data, cursor + 8)
        name = string_at(data, cursor + nameoffset)
        for kind, offset, size in commands(data, header):
            if kind == 0x1B:
                images[name] = str(uuid.UUID(bytes=data[offset + 8:offset + 24])).upper()
            elif kind == 0x19:
                segname, address, length, fileoff, filesize = struct.unpack_from("<16sQQQQ", data, offset + 8)
                if filesize:
                    segments.append((address, filesize, fileoff))
    expected_images = {"com.apple.iokit.IO80211Family": family_uuid,
                       "com.apple.driver.AppleBCMWLANCoreMac": core_uuid}
    for image, expected_uuid in expected_images.items():
        if images.get(image) != expected_uuid.upper():
            raise ValueError(f"Native {image} UUID changed: {images.get(image)}; expected {expected_uuid}")
    output = subprocess.run(["nm", "-n", str(path)], check=True, capture_output=True, text=True).stdout
    symbols = {}
    for line in output.splitlines():
        match = re.match(r"^([0-9a-fA-F]{16})\s+\S\s+(\S+)$", line)
        if match:
            symbols[int(match[1], 16)] = match[2]
    address = next((value for value, name in symbols.items() if name == NATIVE_VTABLE), None)
    if address is None:
        raise ValueError("Native BCM proximity vtable symbol not found")

    def file_offset(value):
        for base, length, fileoff in segments:
            if base <= value < base + length:
                return fileoff + value - base
        raise ValueError(f"No file-backed KC segment for {value:#x}")

    slots = {}
    for slot in range(0, LAST_NATIVE_SLOT + 8, 8):
        pointer = struct.unpack_from("<Q", data, file_offset(address + 16 + slot))[0]
        # This pinned x86_64 fileset uses kernel cache chained pointers.
        target = 0xFFFFFF8000100000 + (pointer & 0x3FFFFFFF)
        if target not in symbols:
            raise ValueError(f"Unknown native vtable pointer at {slot:#x}")
        slots[slot] = symbols[target]
    return slots, expected_images


def signature(symbol):
    """Strip only the owning class; preserve constness and encoded arguments."""
    match = re.match(r"__ZN(K?)(\d+)", symbol)
    if not match:
        raise ValueError(f"Unexpected virtual symbol {symbol}")
    cursor = match.end() + int(match[2])
    return match[1] + symbol[cursor:]


def method_name(symbol):
    value = signature(symbol).lstrip("K")
    match = re.match(r"(\d+)", value)
    if not match:
        return value[:2]  # Constructors/destructors.
    start = match.end()
    return value[start:start + int(match[1])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--object", type=Path, default=ROOT / "build/SimpleMtkWlan.build/Debug/AirportMtkWlan.build/Objects-normal/x86_64/AirportMtkAwdlInterface.o")
    parser.add_argument("--kc", type=Path, default=Path("/System/Library/KernelCollections/BootKernelExtensions.kc"))
    parser.add_argument("--native-vtable", type=Path, help="Optional earlier text snapshot to verify against the current KC")
    parser.add_argument("--family-uuid", default=FAMILY_UUID)
    parser.add_argument("--core-uuid", default=CORE_UUID)
    parser.add_argument("--output", type=Path, help="Save a JSON result")
    args = parser.parse_args()
    candidate = compiled_slots(args.object)
    native, images = native_slots(args.kc, args.family_uuid, args.core_uuid)
    if args.native_vtable:
        snapshot = {}
        for line in args.native_vtable.read_text().splitlines():
            match = re.match(r"(0x[0-9a-f]+) 0x[0-9a-f]+ (.+)", line)
            if match and int(match[1], 16) <= LAST_NATIVE_SLOT:
                snapshot[int(match[1], 16)] = match[2]
        if snapshot != native:
            raise ValueError("Earlier native vtable snapshot disagrees with the current pinned KC")
    for slot, name in ANCHORS.items():
        if method_name(native[slot]) != name:
            raise ValueError(f"Native anchor {slot:#x} changed: {native[slot]}")
    mismatches = [{"slot": hex(slot), "candidate": candidate[slot], "native": symbol}
                  for slot, symbol in native.items() if signature(candidate[slot]) != signature(symbol)]
    result = {"passed": not mismatches, "slots_checked": len(native),
              "last_slot": hex(LAST_NATIVE_SLOT), "native_uuids": images,
              "object": str(args.object.resolve()),
              "object_sha256": hashlib.sha256(args.object.read_bytes()).hexdigest(),
              "mismatches": mismatches,
              "limitation": "Static vtable layout/signature verification only; no live ABI, lifecycle, or RF validation."}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    if mismatches:
        print(json.dumps(result, indent=2))
        return 1
    print(f"PASS {len(native)} compiled AWDL virtual slots through {LAST_NATIVE_SLOT:#x}; "
          "native signatures, anchors, and pinned IO80211/BCM UUIDs match. Static layout only.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError, struct.error) as error:
        print(f"AWDL ABI check failed: {error}", file=sys.stderr)
        sys.exit(1)
