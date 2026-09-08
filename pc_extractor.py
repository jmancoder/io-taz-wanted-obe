import json
import os
from pathlib import Path
from typing import NamedTuple

from .binary_reader import BinaryReader


class PackageHeader(NamedTuple):
    package_id: int
    alignment: int
    flags: int
    file_count: int
    record_array_off: int
    tag_array_off: int
    tag_count: int
    block_map_off: int
    block_map_size: int
    path_array_off: int
    record_array_size: int
    start_sector: int
    build_number: int


class FileRecord(NamedTuple):
    data_off: int
    crc: int
    data_size: int
    path_off_rel: int
    tag_count: int
    tag_off_rel: int
    build_time: int


def read_header(bs: BinaryReader) -> PackageHeader:
    package_id = bs.read_uint32()
    alignment = bs.read_uint32()
    flags = bs.read_uint32()
    file_count = bs.read_uint32()
    record_off = bs.read_uint32()
    tag_off = bs.read_uint32()
    bs.read_uint32()
    tag_count = bs.read_uint32()
    block_map_off = bs.read_uint32()
    block_map_size = bs.read_uint32()
    path_array_off = bs.read_uint32()
    record_size = bs.read_uint32()
    start_sector = bs.read_uint32()
    build_number = bs.read_uint32()
    bs.read_uint32()
    return PackageHeader(
        package_id,
        alignment,
        flags,
        file_count,
        record_off,
        tag_off,
        tag_count,
        block_map_off,
        block_map_size,
        path_array_off,
        record_size,
        start_sector,
        build_number,
    )


def read_file_record(bs: BinaryReader) -> FileRecord:
    data_off = bs.read_uint32()
    crc = bs.read_uint32()
    data_size = bs.read_uint32()
    path_off_rel = bs.read_uint32()
    tag_count = bs.read_uint32()
    tag_off_rel = bs.read_uint32()
    build_time = bs.read_uint64()
    return FileRecord(
        data_off, crc, data_size, path_off_rel, tag_count, tag_off_rel, build_time
    )


def extract_pc(input_path: Path, output_dir: Path) -> int:
    with open(input_path, "rb") as f:
        bs = BinaryReader(f.read())

    header = read_header(bs)
    bs.seek(header.record_array_off * header.alignment)
    file_records = [read_file_record(bs) for _ in range(header.file_count)]

    manifest_dict: dict[int, dict] = {}
    extracted_file_count = 0
    for record in file_records:
        if record.tag_count == 0:
            continue

        # Read tags
        bs.seek((header.tag_array_off * header.alignment) + record.tag_off_rel)
        tags = [bs.read_cstring() for _ in range(record.tag_count)]

        # Read and resolve path
        bs.seek((header.path_array_off * header.alignment) + record.path_off_rel)
        file_path = bs.read_cstring()

        # Extract file
        output_path = output_dir / input_path.stem / Path(file_path)
        os.makedirs(output_path.parent, exist_ok=True)
        bs.seek(record.data_off * header.alignment)
        with open(output_path, "wb") as f:
            f.write(bs.read(record.data_size))
        extracted_file_count += 1

        manifest_dict[record.crc] = {
            "path": file_path,
            "tags": tags,
            "offset": record.data_off * header.alignment,
            "size": record.data_size,
        }

    # Create manifest file
    with open(output_dir / f"{header.package_id}.json", "wt") as f:
        json.dump(manifest_dict, f, indent=4)
    return extracted_file_count
