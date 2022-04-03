import codecs

from .cell import deserialize_boc, Slice, deserialize_cell_from_json

def render_tvm_element(element_type, element):
    if element_type in ["num", "number", "int"]:
      element = str(int(str(element), 0))
      return {'@type': 'tvm.stackEntryNumber', 'number': {'@type': 'tvm.numberDecimal', 'number': element}}
    elif element_type == "cell":
      element = deserialize_cell_from_json(element)
      element_data = codecs.decode(codecs.encode(element.serialize_boc(has_idx=False), 'base64'), 'utf-8').replace('\n', '')
      return {'@type': 'tvm.stackEntryCell', 'cell': {'@type': 'tvm.Cell', 'bytes': element_data}}
    elif element_type == "slice":
      element = deserialize_cell_from_json(element)
      element_data = codecs.decode(codecs.encode(element.serialize_boc(has_idx=False), 'base64'), 'utf-8').replace('\n', '')
      return {'@type': 'tvm.stackEntrySlice', 'slice': {'@type': 'tvm.Slice', 'bytes': element_data}}
    elif element_type == "tvm.Slice":
      return {'@type': 'tvm.stackEntrySlice', 'slice': {'@type': 'tvm.Slice', 'bytes': element}}
    elif element_type == "tvm.Cell":
      return {'@type': 'tvm.stackEntryCell', 'cell': {'@type': 'tvm.Cell', 'bytes': element}}
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
    data = codecs.encode(t["cell"]["bytes"],'utf8')
    data = codecs.decode(data, 'base64')
    s = Slice(deserialize_boc(data))
    return ["cell", {'bytes':t["cell"]["bytes"], 'object':s.serialize_to_object()}]
  elif t["@type"] == "tvm.stackEntryCell":
    data = codecs.encode(t["cell"]["bytes"],'utf8')
    data = codecs.decode(data, 'base64')
    cell = deserialize_boc(data)
    return ["cell", {'bytes':t["cell"]["bytes"], 'object':cell.serialize_to_object()}]
  elif t["@type"] == "tvm.stackEntryTuple":
    return ["tuple", t["tuple"]]
  elif t["@type"] == "tvm.stackEntryList":
    return ["list", t["list"]]
  else:
    raise Exception("Unknown type")

def serialize_tvm_stack(tvm_stack):
  stack = []
  for t in tvm_stack:
    stack.append(serialize_tvm_element(t))
  return stack
