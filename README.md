# TVM value types
Telegram Open Network Virtual Machine has 7 value types:
1. Integer
2. Cell
3. Tuple
4. Null
5. Slice
6. Builder
7. Continuation

This library is collection of utilits for handling those types.

# Cell and Slice
`tvm_valuetypes.cell` has class `Cell` and functions to work with cells:
`deserialize_boc`, `cell.serialize_boc`, `cell.serialize_to_object`, `cell.serialize_to_json`, `deserialize_cell_from_json`
```
from tvm_valuertypes.cell import Cell, deserialize_boc
serialized_cell = bytes.fromhex("B5EE9C72410102010007000102000100024995C5FE15")
cell1 = deserialize_boc(serialized_c1)
cell1
serialization_with_index = cell1.serialize_boc(has_idx=True, hash_crc32=True, has_cache_bits=False, flags=0 )
serialization_with_index
cell2 = deserialize_boc(serialized_c2)
cell2 == cell1
cell2.serialize_to_object()
```
## HashMaps (Dictionaries)
Cell may represent special 'virtual' value type, HashMap, which can be used for storing key-value container in the Cell.

`tvm_valuetypes.dict_utils` has special method `parse_hashmap` for dealing with hashmaps. Note the difference between `Hashmap` and `HashmapE`.

```
from tvm_valuertypes.cell import Cell
from tvm_valuertypes.dict_utils import parse_hashmap
test_dict = bytes.fromhex("B5EE9C7241010A01002D00020120010202014803040003FC0202014805060003F5FE02014807080003DB24020120090900035FF800030020CB8CA892")
dict_cell = deserialize_boc(test_dict)
parsed_dict = {}
parse_hashmap(dict_cell, 8, parsed_dict)
parsed_dict
```




