from bitarray import bitarray


def read_arbitrary_uint(n, ser):
    x = 0
    for i in range(n):
        x <<= 1
        r = ser.pop(0)
        x += r
    return x, ser


def deser_unary(ser):
    """
      unary_zero$0 = Unary ~0;
      unary_succ$1 {n:#} x:(Unary ~n) = Unary ~(n + 1);
    """
    n = 0
    while True:
        r = ser.pop(0)
        if r:
            n += 1
        else:
            return n, ser


def deser_hmlabel(ser, m):
    """
      hml_short$0 {m:#} {n:#} len:(Unary ~n) s:(n * Bit) = HmLabel ~n m;
      hml_long$10 {m:#} n:(#<= m) s:(n * Bit) = HmLabel ~n m;
      hml_same$11 {m:#} v:Bit n:(#<= m) = HmLabel ~n m;
    """
    _type = ''
    k = ser.pop(0)
    s = bitarray()
    if k:
        k = ser.pop(0)
        if k:
            _type = 'same'
        else:
            _type = 'long'
    else:
        _type = 'short'
    if _type == 'short':
        _len, ser = deser_unary(ser)
        s, ser = ser[:_len], ser[_len:]
    elif _type == 'long':
        _len, ser = read_arbitrary_uint(m.bit_length(), ser)
        s, ser = ser[:_len], ser[_len:]
    else:
        v, ser = ser[0:1], ser[1:]
        _len, ser = read_arbitrary_uint(m.bit_length(), ser)
        s = v * _len
    return _len, s, ser


def deser_hashmapnode(cell, m, ret_dict, prefix, max_elements):
    """
      hmn_leaf#_ {X:Type} value:X = HashmapNode 0 X;
      hmn_fork#_ {n:#} {X:Type} left:^(Hashmap n X) right:^(Hashmap n X) = HashmapNode (n + 1) X;
    """
    if len(ret_dict) >= max_elements:
        return
    if m == 0:  # leaf
        ret_dict[prefix.to01()] = cell
    else:  # fork
        l_prefix, r_prefix = prefix.copy(), prefix.copy()
        l_prefix.append(False)
        r_prefix.append(True)
        parse_hashmap(
            cell.refs[0].copy(),
            m - 1,
            ret_dict,
            l_prefix,
            max_elements)
        parse_hashmap(
            cell.refs[1].copy(),
            m - 1,
            ret_dict,
            r_prefix,
            max_elements)


def parse_hashmap(cell, bitlength, ret_dict, prefix, max_elements=10000):
    """
      hm_edge#_ {n:#} {X:Type} {l:#} {m:#} label:(HmLabel ~l n)
           {n = (~m) + l} node:(HashmapNode m X) = Hashmap n X;
    """
    _len, suffix, cell.data.data = deser_hmlabel(cell.data.data, bitlength)
    prefix.extend(suffix)
    m = bitlength - _len
    deser_hashmapnode(cell.copy(), m, ret_dict, prefix.copy(), max_elements)


def test_parse_hashmap():
    test_dict1 = "B5EE9C7241010A01002D00020120010202014803040003FC0202014805060003F5FE02014807080003DB24020120090900035FF800030020CB8CA892"
    import codecs
    test_dict1 = codecs.decode(test_dict1, 'hex')
    from cell import deserialize_boc
    dict1_cell = deserialize_boc(test_dict1)
    parsed_dict = {}
    parse_hashmap(dict1_cell, 8, parsed_dict)
    print(parsed_dict)

    test_dict1 = "B5EE9C7241010101000B000012A00000006400000001FC00C1D4"
    test_dict1 = codecs.decode(test_dict1, 'hex')
    dict1_cell = deserialize_boc(test_dict1)
    parsed_dict = {}
    parse_hashmap(dict1_cell, 32, parsed_dict)
    # assert parsed_dict == {'00000000': bitarray('00000000'), '00000001': bitarray('00000000'), '00000011': bitarray('11111111'), '00001000': bitarray('01100100'), '00111111': bitarray('01111111'), '11111111': bitarray('00000000')}
    print(parsed_dict)
