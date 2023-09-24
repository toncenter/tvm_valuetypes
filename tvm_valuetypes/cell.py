import codecs
import json
from hashlib import sha256
from math import ceil

from bitarray import bitarray
from crc32c import crc32 as crc32c

reach_boc_magic_prefix = b'\xB5\xEE\x9C\x72'
lean_boc_magic_prefix = b'\x68\xff\x65\xf3'
lean_boc_magic_prefix_crc = b'\xac\xc3\xa7\x28'


class CellData:
    def __init__(self, max_length=1023):
        self.data = bitarray()
        self.max_length = max_length

    def put_bool(self, element):
        if not (self.max_length is None):
            if len(self.data) >= self.max_length:
                raise Exception("Cell overflow")
        self.data.append(element)

    def put_arbitrary_uint(self, uint, bitsize):
        if bitsize <= 0 or (2 ** bitsize - 1 < uint):
            raise Exception(
                "Not enough bits (%d) to encode integer (%d)" %
                (bitsize, uint))
        for i in range(bitsize, 0, -1):
            k = (2 ** (i - 1))
            if uint // k == 1:
                self.put_bool(1)
                uint -= k
            else:
                self.put_bool(0)

    def put_uint8(self, uint):
        self.put_arbitrary_uint(uint, 8)

    def put_bytes(self, _bytes):
        for byte in _bytes:
            self.put_uint8(byte)

    def put_arbitrary_int(self, _int, bitsize):
        if bitsize == 1:
            if _int in [0, -1]:
                self.put_bool(_int == -1)
                return
            else:
                raise Exception(
                    "Not enough bits (%d) to encode integer (%d)" %
                    (bitsize, _int))
        if _int < 0:
            self.put_bool(1)
            s = 2 ** (bitsize - 1)
            self.put_arbitrary_uint(s - _int, bitsize - 1)
        else:
            self.put_bool(0)
            self.put_arbitrary_uint(_int, bitsize - 1)

    def concatenate(self, another_cell_data):
        if self.length() + another_cell_data.length() > 1023:
            raise Exception(
                "Not enough bits to concantenate cells: %d + %d" %
                (self.length(), another_cell_data.length()))
        self.data.extend(another_cell_data.data)

    def top_up(self):
        l = len(self.data)
        additional_bits = ceil(l / 8) - l // 8
        if ceil(l / 8) == 128:
            additional_bits -= 1
        for i in range(additional_bits):
            if i == 0:
                self.put_bool(1)
            else:
                self.put_bool(0)

    def copy(self):
        cd = CellData()
        cd.data = bitarray(self.data)
        return cd

    def length(self):
        return len(self.data)

    def top_upped_bytes(self):
        t = self.copy()
        t.top_up()
        return t.data.tobytes()

    def from_bytes(self, data, top_upped=False):
        self.data = bitarray()
        self.data.frombytes(data)
        if top_upped:
            x = self.data.pop()
            while not x:
                x = self.data.pop()

    def __eq__(self, another_cell_data):
        return (self.data.tobytes() == another_cell_data.data.tobytes()) and (
            self.length() == another_cell_data.length())

    def __len__(self):
        return self.length()

    def __repr__(self):
        if self.length() % 8:
            x = self.copy()
            x.top_up()
            return "%s_" % (x.data.tobytes())
        else:
            return "%s" % (self.data.tobytes())


class Cell:
    def __init__(self):
        self.data = CellData()
        self.refs = []
        self.special = False

    def level(self):
        if self.is_special():
            raise NotImplementedError('Calculating level not implemented for special cells')
        max_level = 0
        for k in self.refs:
            if k.level() > max_level:
                max_level = k.level()
        return max_level

    def is_special(self):
        return self.special

    def is_explicitly_stored_hashes(self):
        return 0

    def depth(self):
        max_depth = 0
        if len(self.refs) > 0:
            for k in self.refs:
                if k.depth() > max_depth:
                    max_depth = k.depth()
            max_depth = max_depth + 1
        return max_depth

    def encoded_depth(self):
        return (self.depth() // 256).to_bytes(1, "big") + \
            (self.depth() % 256).to_bytes(1, "big")

    def concatenate(self, another_cell):
        self.data.concatenate(another_cell.data)
        self.refs = self.refs + another_cell.refs

    def refs_descriptor(self):
        return (len(self.refs) + self.is_special() *
                8 + self.level() * 32).to_bytes(1, "big")

    def bits_descriptor(self):
        return ((len(self.data) // 8) +
                ceil(len(self.data) / 8)).to_bytes(1, "big")

    def data_with_descriptors(self):
        return self.refs_descriptor() + self.bits_descriptor() + self.data.top_upped_bytes()

    def repr(self):
        ret = self.data_with_descriptors()
        for k in self.refs:
            ret += k.encoded_depth()
        for k in self.refs:
            ret += k.hash()
        return ret

    def hash(self):
        return self._recursive_hash()[2]

    def _recursive_hash(self):
        # retutrns tuple (level, depth, hash) of current cell
        if self.is_special():
            raise NotImplementedError('Calculating level not implemented for special cells')
        hasher = sha256()
        if len(self.refs) == 0:
            self_data = b'\x00' + self.bits_descriptor() + self.data.top_upped_bytes()
            hasher.update(self_data)
            # level and depth is zero
            return (0, 0, hasher.digest())
        else:
            children = [ref._recursive_hash() for ref in self.refs]
            max_level = 0
            max_depth = 0
            depth_block = b''
            hashes_block = b''
            for depth, level, ref_hash in children:
                if level > max_level:
                    max_level = level
                if depth > max_depth:
                    max_depth = depth
                depth_block += (depth // 256).to_bytes(1, "big") + (depth % 256).to_bytes(1, "big")
                hashes_block += ref_hash

            self_data = (len(self.refs) + max_level * 32).to_bytes(1, "big") + self.bits_descriptor() + self.data.top_upped_bytes()
            hasher.update(self_data + depth_block + hashes_block)
            return (max_depth + 1, max_level, hasher.digest())

    def serialize_for_boc(self, cells_index, ref_size):
        # This is not serialization of the cell as boc with this cell as root_cell
        # it is serialization of the cell to be used in boc serialization
        ret = self.data_with_descriptors()
        if self.is_explicitly_stored_hashes():
            raise NotImplementedError(
                "Do not support explicitly stored hashes yet")
        for k in self.refs:
            ref_hash = k.hash()
            ref_index_int = cells_index[ref_hash]
            ref_index_hex = f"{ref_index_int:x}"
            if len(ref_index_hex) % 2:
                ref_index_hex = "0" + ref_index_hex
            reference = bytes.fromhex(ref_index_hex)
            ret += reference
        return ret

    def serialize_for_boc_size(self, cells_index, ref_size):
        return len(self.serialize_for_boc(cells_index, ref_size))

    def build_indexes(self):
        def move_to_end(index_hashmap, topological_order_array, target):
            target_index = index_hashmap[target]
            for hash in index_hashmap:
                if index_hashmap[hash] > target_index:
                    index_hashmap[hash] -= 1
            index_hashmap[target] = len(topological_order_array) - 1
            data = topological_order_array[target_index]
            topological_order_array.append(data)
            for subcell in data[1].refs:
                index_hashmap, topological_order_array = move_to_end(index_hashmap,
                                                                topological_order_array, subcell.hash())
            return index_hashmap, topological_order_array

        def tree_walk(cell, topological_order_array, index_hashmap, parent_hash=None):
            cell_hash = cell.hash()
            if cell_hash in index_hashmap:
                if parent_hash:
                    if index_hashmap[parent_hash] > index_hashmap[cell_hash]:
                        index_hashmap, topological_order_array = \
                            move_to_end(index_hashmap, topological_order_array, cell_hash)
                return topological_order_array, index_hashmap
            index_hashmap[cell_hash] = len(topological_order_array)
            topological_order_array.append((cell_hash, cell))
            for subcell in cell.refs:
                topological_order_array, index_hashmap = tree_walk(
                    subcell, topological_order_array, index_hashmap, cell_hash)
            return topological_order_array, index_hashmap

        return tree_walk(self, [], {})

    def serialize_boc(
            self,
            has_idx=True,
            hash_crc32=True,
            has_cache_bits=False,
            flags=0):
        # This is serialization of the cell to boc as root_cell
        topological_order, index_hashmap = self.build_indexes()
        cells_num = len(topological_order)
        s = cells_num.bit_length()  # Minimal number of bits to represent reference (unused?)
        s_bytes = max(ceil(s / 8), 1)
        full_size = 0
        cell_sizes = {}
        for (_hash, subcell) in topological_order:
            cell_sizes[_hash] = subcell.serialize_for_boc_size(
                index_hashmap, s_bytes)
            full_size += cell_sizes[_hash]

        offset_bits = full_size.bit_length()  # Minimal number of bits to encode offset
        offset_bytes = max(ceil(offset_bits / 8), 1)
        # has_idx 1bit, hash_crc32 1bit,  has_cache_bits 1bit, flags 2bit,
        # s_bytes 3 bit
        serialization = CellData(max_length=None)
        serialization.put_bytes(reach_boc_magic_prefix)
        serialization.put_arbitrary_uint(bool(has_idx), 1)
        serialization.put_arbitrary_uint(bool(hash_crc32), 1)
        serialization.put_arbitrary_uint(bool(has_cache_bits), 1)
        serialization.put_arbitrary_uint(flags, 2)
        serialization.put_arbitrary_uint(s_bytes, 3)
        serialization.put_uint8(offset_bytes)
        serialization.put_arbitrary_uint(cells_num, s_bytes * 8)
        serialization.put_arbitrary_uint(1, s_bytes * 8)  # One root for now
        serialization.put_arbitrary_uint(0, s_bytes * 8)  # Complete BOCs only
        serialization.put_arbitrary_uint(full_size, offset_bytes * 8)
        serialization.put_arbitrary_uint(0, s_bytes * 8)  # Root should have index 0
        if has_idx:
            for (_hash, subcell) in topological_order:
                serialization.put_arbitrary_uint(cell_sizes[_hash], offset_bytes * 8)
        for (_hash, subcell) in topological_order:
            refcell_ser = subcell.serialize_for_boc(index_hashmap, offset_bytes)
            for byte in refcell_ser:
                serialization.put_uint8(byte)
        ser_arr = serialization.top_upped_bytes()
        if hash_crc32:
            ser_arr += crc32c(ser_arr).to_bytes(4, "little")
        return ser_arr

    def copy(self):
        ret = Cell()
        ret.data = self.data.copy()
        ret.refs = self.refs.copy()
        ret.special = self.special
        return ret

    def __repr__(self):
        return "<Cell refs_num: %d, data: %s>" % (
            len(self.refs), repr(self.data))

    def serialize_to_object(self):
        ret = {'data': {'b64': b'', 'len': 0}, 'refs': [], 'special': False}
        for r in self.refs:
            ret['refs'].append(r.serialize_to_object())
        ret['data']['b64'] = codecs.decode(
            codecs.encode(
                self.data.data.tobytes(),
                'base64'),
            'utf8').replace(
            '\n',
            '')
        ret['data']['len'] = len(self.data)
        ret['special'] = self.is_special()
        return ret

    def serialize_to_json(self):
        return json.dumps(self.serialize_to_object())

    def __eq__(self, another_cell):
        if not len(self.refs) == len(another_cell.refs):
            return False
        for i in range(len(self.refs)):
            if not self.refs[i] == another_cell.refs[i]:
                return False
        return self.data == another_cell.data


def test_boc_serialization():
    c0 = Cell()
    res = c0.serialize_boc(has_idx=False)
    reference_serialization_0 = bytes.fromhex(
        "B5EE9C724101010100020000004CACB9CD")
    assert res == reference_serialization_0, "Wrong empty cell boc-serialization"

    c1 = Cell()
    c1.data.put_uint8(0)
    res = c1.serialize_boc(has_idx=False)
    reference_serialization_1 = bytes.fromhex(
        "B5EE9C7241010101000300000200D367DC41")
    assert res == reference_serialization_1, "Wrong <b 0 8 u, b> cell boc-serialization"

    c1 = Cell()
    c2 = Cell()
    c1.data.put_uint8(0)
    c2.data.put_uint8(73)
    c1.refs.append(c2)
    res = c1.serialize_boc(has_idx=False)
    reference_serialization_2 = bytes.fromhex(
        "B5EE9C72410102010007000102000100024995C5FE15")
    assert res == reference_serialization_2, "Wrong '<b 0 8 u, <b 73 8 u, b> ref, b>' cell boc-serialization"

def test_cell_hash():
    cell_data = 'te6ccsEBFwEAYAAEBQQFBQQFBAQEBAQEBAQEBAQFBAQEAwECyQEBBMsXAgECEgMBBMsXBAEEywcF\nAQIUBgEEywcHAQIBCAECJQkBAsgKAQKhCwECAQwBAiENAQIiDgECqA8BAgEQAQIhEQECARIBBIAD\nEwECqBQBAgEVAQIhFgACIX1S8I0='
    cell_boc = codecs.decode(codecs.encode(cell_data, 'utf8'), 'base64')
    cell = deserialize_boc(cell_boc)
    assert 'MIrkspKfhLvHwcH+yryp0gZZR3vjKOYQ5VTAbqF8zB4=\n' == codecs.decode(codecs.encode(cell.hash(), 'base64'), 'utf-8')


def parse_flags(serialization):
    header_byte, serialization = serialization[0], serialization[1:]
    has_idx, hash_crc32, has_cache_bits = header_byte & 128, header_byte & 64, header_byte & 32
    header_byte %= 32
    flags, size_bytes = header_byte >> 3, header_byte % 8
    return (has_idx, hash_crc32, has_cache_bits,
            flags, size_bytes), serialization


def deserialize_cell_data(ser, index_size):
    d1, d2, ser = ser[0], ser[1], ser[2:]
    level, d1 = (d1 // 32), d1 % 32
    h, d1 = (d1 // 16), d1 % 16
    if h > 0:
        raise NotImplementedError(
            "Cell with explicit hash references are not supported yet")
    s, r = (d1 // 8), d1 % 8
    if r > 4:
        raise NotImplementedError(
            "Cell with explicit hash references are not supported yet (r>4)")
    if d2 % 2:
        data_size = (d2 + 1) // 2
        not_full = True
    else:
        data_size = d2 // 2
        not_full = False
    cell_data, ser = ser[:data_size], ser[data_size:]
    c = Cell()
    c.special = s > 0
    c.data.from_bytes(cell_data, top_upped=not_full)
    for i in range(r):
        ref_index, ser = int.from_bytes(
            ser[:index_size], "big"), ser[index_size:]
        c.refs.append(ref_index)
    return c, ser


def substitute_indexes_with_cells(cells):
    for cell in cells[::-1]:
        for i, r in enumerate(cell.refs):
            cell.refs[i] = cells[r]
    return cells


def deserialize_boc(boc):
    bocs_prefixes = [
        reach_boc_magic_prefix,
        lean_boc_magic_prefix,
        lean_boc_magic_prefix_crc]
    prefix, boc = boc[:4], boc[4:]
    assert (prefix in bocs_prefixes), "Unknown boc prefix"
    if prefix == reach_boc_magic_prefix:
        (has_idx, hash_crc32, has_cache_bits,
         flags, size_bytes), boc = parse_flags(boc)
        root_list = True
    elif prefix == lean_boc_magic_prefix:
        (has_idx, hash_crc32, has_cache_bits, flags,
         size_bytes), boc = (1, 0, 0, 0, boc[0]), boc[1:]
        root_list = False
    elif prefix == lean_boc_magic_prefix_crc:
        (has_idx, hash_crc32, has_cache_bits, flags,
         size_bytes), boc = (1, 1, 0, 0, boc[0]), boc[1:]
        root_list = False
    off_bytes, boc = boc[0], boc[1:]
    cells_num, boc = int.from_bytes(boc[0:size_bytes], "big"), boc[size_bytes:]
    roots_num, boc = int.from_bytes(boc[0:size_bytes], "big"), boc[size_bytes:]
    absent_num, boc = int.from_bytes(
        boc[0:size_bytes], "big"), boc[size_bytes:]
    assert absent_num == 0
    tot_cells_size, boc = int.from_bytes(
        boc[0:off_bytes], "big"), boc[off_bytes:]
    if root_list:
        if roots_num > 1:
            raise NotImplementedError(
                "Only 1 root supported for now (%d)" %
                roots_num)
        roots_indexes = []
        for i in range(roots_num):
            ri, boc = int.from_bytes(
                boc[0:size_bytes], "big"), boc[size_bytes:]
            roots_indexes.append(ri)
    else:
        roots_indexes = [0]
    if has_idx:
        offsets = []
        for i in range(cells_num):
            o, boc = int.from_bytes(boc[0:off_bytes], "big"), boc[off_bytes:]
            offsets.append(o)
    cells = []
    for i in range(cells_num):
        unfinished_cell, boc = deserialize_cell_data(boc, size_bytes)
        cells.append(unfinished_cell)
    cells = substitute_indexes_with_cells(cells)
    # TODO hash_crc32?
    return cells[0]


def deserialize_cell_from_object(data):
    cell = Cell()
    b64 = data['data']['b64']
    cell.data.from_bytes(codecs.decode(codecs.encode(b64, 'utf8'), 'base64'))
    cell.data.data = cell.data.data[:data['data']['len']]
    for r in data['refs']:
        cell.refs.append(deserialize_cell_from_object(r))
    cell.special = data['special']
    return cell


def deserialize_cell_from_json(json_data):
    return deserialize_cell_from_object(json.loads(json_data))


def test_boc_deserialization():
    c1 = Cell()
    c2 = Cell()
    c3 = Cell()
    c4 = Cell()
    c1.data.put_arbitrary_uint(2 ** 25, 26)
    c2.data.put_arbitrary_uint(2 ** 37, 38)
    c3.data.put_arbitrary_uint(2 ** 41, 42)
    c4.data.put_arbitrary_uint(2 ** 44 - 2, 44)
    c2.refs.append(c3)
    c1.refs.append(c2)
    c1.refs.append(c4)
    serialized_c1 = c1.serialize_boc(has_idx=False)

    dc1 = deserialize_boc(serialized_c1)
    assert dc1.data == c1.data
    assert dc1.refs[0].data == c2.data
    assert dc1.refs[1].data == c4.data
    assert dc1.refs[0].refs[0].data == c3.data


class Slice(Cell):
    def __repr__(self):
        return "<Slice refs_num: %d, data: %s>" % (
            len(self.refs), repr(self.data))

    def __init__(self, cell):
        self.data = cell.data.copy()
        self.refs = cell.refs.copy()
        assert cell.special == False
        self.special = cell.special
