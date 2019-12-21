from .cell import deserialize_boc, Slice, deserialize_cell_from_json

def render_tvm_element(element_type, element):
    if element_type in ["num", "number", "int"]:
      element = str(int(str(element), 0))
      return {'@type': 'tvm.stackEntryNumber', 'number': {'@type': 'tvm.numberDecimal', 'number': element}}
    elif element_type == "cell":
      element = deserialize_cell_from_json(element)
      return {'@type': 'tvm.stackEntryCell', 'cell': {'@type': 'tvm.Cell', 'bytes': element.serialize_boc(has_idx=False)}}
    elif element_type == "slice":
      element = deserialize_cell_from_json(element)
      return {'@type': 'tvm.stackEntrySlice', 'slice': {'@type': 'tvm.Slice', 'bytes': element.serialize_boc(has_idx=False)}}
    else:
      raise NotImplemented()

def render_tvm_stack(stack_data):
  """
    Elements like that are expected:
    [["num", 300], ["cell", "0x"], ["dict", {...}]]
    Currently only "num", "cell" and "slice" are supported.
    To be implemented:
      T: "list", "tuple", "num", "cell", "slice", "dict", "list"    
  """
  stack = []
  for t in stack_data:
    stack.append(render_tvm_element(*t))
  return stack

def serialize_tvm_element(t):
  if not "@type" in t:
    raise Exception("Not TVM stack element")
  if t["@type"] == "tvm.stackEntryNumber":
    return ["num", hex(int(t["number"]["number"]))]
  elif t["@type"] == "tvm.stackEntrySlice":
    data = t["slice"]["bytes"]
    data = codecs.decode(codecs.encode(data,'utf8'), 'base64')
    s = Slice(deserialize_boc(data))
    return ["slice", s]
  elif t["@type"] == "tvm.stackEntryCell":
    data = t["cell"]["bytes"]
    data = codecs.decode(codecs.encode(data,'utf8'), 'base64')
    return ["slice", deserialize_boc(data)]
  elif t["@type"] == "tvm.stackEntryTuple":
    return ["slice", t["tuple"]]
  elif t["@type"] == "tvm.stackEntryList":
    return ["slice", t["list"]]
  else:
    raise Exception("Unknown type")

def serialize_tvm_stack(tvm_stack):
  stack = []
  for t in tvm_stack:
    stack.append(serialize_tvm_element(t))
  return stack
