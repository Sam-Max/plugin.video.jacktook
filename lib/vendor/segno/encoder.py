#
# Copyright (c) 2016 - 2024 -- Lars Heuer
# All rights reserved.
#
# License: BSD License
#
"""\
QR Code and Micro QR Code encoder.

DOES NOT belong to the public API.

"QR Code" and "Micro QR Code" are registered trademarks of DENSO WAVE INCORPORATED.
"""
from operator import itemgetter, gt, lt, xor
from functools import partial, reduce
from itertools import islice, chain, product
import re
import math
import codecs
from collections import namedtuple
from . import consts
from itertools import zip_longest
import sys
_MAX_PENALTY_SCORE = sys.maxsize
del sys

__all__ = ('encode', 'encode_sequence', 'DataOverflowError')


class DataOverflowError(ValueError):
    """\
    Indicates a problem that the provided data does not fit into the
    provided QR Code version or the data is too large in general.

    This exception is inherited from :py:exc:`ValueError` and is only raised
    if the data does not fit into the provided (Micro) QR Code version.

    Basically it is sufficient to catch a :py:exc:`ValueError`.
    """


Code = namedtuple('Code', 'matrix version error mask segments')


def encode(content, error=None, version=None, mode=None, mask=None,
           encoding=None, eci=False, micro=None, boost_error=True):
    version = normalize_version(version)
    if not micro and micro is not None and version in consts.MICRO_VERSIONS:
        raise ValueError(f'A Micro QR Code version ("{get_version_name(version)}") '
                         'is provided but parameter "micro" is False')
    if micro and version is not None and version not in consts.MICRO_VERSIONS:
        raise ValueError(f'Illegal Micro QR Code version "{get_version_name(version)}"')
    error = normalize_errorlevel(error, accept_none=True)
    mode = normalize_mode(mode)
    if mode is not None and version is not None \
            and not is_mode_supported(mode, version):
        raise ValueError(f'Mode "{get_mode_name(mode)}" is not available in version "{get_version_name(version)}"')
    if error == consts.ERROR_LEVEL_H and (micro or version in consts.MICRO_VERSIONS):
        raise ValueError('Error correction level "H" is not available for Micro QR Codes')
    if eci and (micro or version in consts.MICRO_VERSIONS):
        raise ValueError('The ECI mode is not available for Micro QR Codes')
    segments = prepare_data(content, mode, encoding)
    guessed_version = find_version(segments, error, eci=eci, micro=micro)
    if version is None:
        version = guessed_version
    elif guessed_version > version:
        raise DataOverflowError(f'The provided data does not fit into version "{get_version_name(version)}"'
                                f'Proposal: version {get_version_name(guessed_version)}')
    if error is None and version != consts.VERSION_M1:
        error = consts.ERROR_LEVEL_L
    is_micro = version < 1
    mask = normalize_mask(mask, is_micro)
    return _encode(segments, error, version, mask, eci, boost_error)


def encode_sequence(content, error=None, version=None, mode=None, mask=None,
                    encoding=None, eci=False, boost_error=True, symbol_count=None):
    def one_item_segments(chunk, mode):
        segs = Segments()
        segs.add_segment(make_segment(chunk, mode=mode, encoding=encoding))
        return segs

    def divide_into_chunks(data, num):
        k, m = divmod(len(data), num)
        return [data[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(num)]

    def calc_qrcode_bit_length(char_count, ver_range, mode, encoding=None,
                               is_eci=False, is_sa=False):
        overhead = 4  # Mode indicator for QR Codes, only
        # Number of bits in character count indicator
        overhead += consts.CHAR_COUNT_INDICATOR_LENGTH[mode][ver_range]
        if is_eci and mode == consts.MODE_BYTE and encoding != consts.DEFAULT_BYTE_ENCODING:
            overhead += 4  # ECI indicator
            overhead += 8  # ECI assignment no
        if is_sa:
            # 4 bit for mode, 4 bit for the position, 4 bit for total number of symbols
            # 8 bit for parity data
            overhead += 5 * 4
        bits = 0
        if mode == consts.MODE_NUMERIC:
            num, remainder = divmod(char_count, 3)
            bits += num * 10 + (4 if remainder == 1 else 7)
        elif mode == consts.MODE_ALPHANUMERIC:
            num, remainder = divmod(char_count, 2)
            bits += num * 11 + (6 if remainder else 0)
        elif mode == consts.MODE_BYTE:
            bits += char_count * 8
        elif mode in (consts.MODE_KANJI, consts.MODE_HANZI):
            bits += char_count * 13
        return overhead + bits

    def number_of_symbols_by_version(content, version, error, mode):
        length = len(content)
        ver_range = version_range(version)
        bit_length = calc_qrcode_bit_length(length, ver_range, mode, encoding,
                                            is_eci=eci, is_sa=True)
        capacity = consts.SYMBOL_CAPACITY[version][error]
        # Initial result does not contain the overhead of SA mode for all QR Codes
        cnt = int(math.ceil(bit_length / capacity))
        # Overhead of SA mode for all QR Codes
        bit_length += 5 * 4 * (cnt - 1) + (12 * (cnt - 1) if eci else 0)
        return int(math.ceil(bit_length / capacity))

    version = normalize_version(version)
    if version is not None:
        if version < 1:
            raise ValueError('This function does not accept Micro QR Code versions. '
                             f'Provided: "{get_version_name(version)}"')
    elif symbol_count is None:
        raise ValueError('Please provide either a QR Code version or the symbol count')
    if symbol_count is not None and not 1 <= symbol_count <= 16:
        raise ValueError('The symbol count must be in range 1 .. 16')
    error = normalize_errorlevel(error, accept_none=True)
    if error is None:
        error = consts.ERROR_LEVEL_L
    mode = normalize_mode(mode)
    mask = normalize_mask(mask, is_micro=False)
    segments = prepare_data(content, mode, encoding)
    guessed_version = None
    if symbol_count is None:
        try:
            # Try to find a version which fits without using Structured Append
            guessed_version = find_version(segments, error, eci=eci, micro=False)
        except DataOverflowError:
            # Data does fit into a usual QR Code but ignore the error silently,
            # guessed_version is None
            pass
        if guessed_version and guessed_version <= (version or guessed_version):
            # Return iterable of size 1
            return [_encode(segments, error=error, version=(version or guessed_version),
                            mask=mask, eci=eci, boost_error=boost_error)]
    if len(segments.modes) > 1:
        raise ValueError('This function cannot handle more than one mode (yet). Sorry.')
    mode = segments.modes[0]  # CHANGE iff more than one mode is supported!
    # Creating one QR code failed or max_no is not None
    if mode == consts.MODE_NUMERIC:
        content = str(content)
    if symbol_count is not None and len(content) < symbol_count:
        raise ValueError(f'The content is not long enough to be divided into {symbol_count} symbols')
    sa_parity_data = calc_structured_append_parity(content)
    num_symbols = symbol_count or 16
    if version is not None:
        num_symbols = number_of_symbols_by_version(content, version, error, mode)
    if num_symbols > 16:
        raise DataOverflowError(f'The data does not fit into Structured Append version {version}')
    chunks = divide_into_chunks(content, num_symbols)
    if symbol_count is not None:
        segments = one_item_segments(max(chunks, key=len), mode)
        version = find_version(segments, error, eci=eci, micro=False, is_sa=True)
    sa_info = partial(_StructuredAppendInfo, total=len(chunks) - 1,
                      parity=sa_parity_data)
    return [_encode(one_item_segments(chunk, mode), error=error, version=version,
                    mask=mask, eci=eci, boost_error=boost_error,
                    sa_info=sa_info(i)) for i, chunk in enumerate(chunks)]


def _encode(segments, error, version, mask, eci, boost_error, sa_info=None):
    is_micro = version < 1
    sa_mode = sa_info is not None
    buff = Buffer()
    ver = version
    ver_range = version
    if not is_micro:
        ver = None
        ver_range = version_range(version)
    if boost_error:
        error = boost_error_level(version, error, segments, eci, is_sa=sa_mode)
    if sa_mode:
        # ISO/IEC 18004:2015(E) -- 8 Structured Append (page 59)
        for i in sa_info[:3]:
            buff.append_bits(i, 4)
        buff.append_bits(sa_info.parity, 8)
    # ISO/IEC 18004:2015(E) -- 7.4 Data encoding (page 22)
    for segment in segments:
        write_segment(buff, segment, ver, ver_range, eci)
    capacity = consts.SYMBOL_CAPACITY[version][error]
    # ISO/IEC 18004:2015(E) -- 7.4.9 Terminator (page 32)
    write_terminator(buff, capacity, ver, len(buff))
    # ISO/IEC 18004:2015(E) -- 7.4.10 Bit stream to codeword conversion (page 34)
    write_padding_bits(buff, version, len(buff))
    # ISO/IEC 18004:2015(E) -- 7.4.10 Bit stream to codeword conversion (page 34)
    write_pad_codewords(buff, version, capacity, len(buff))
    # ISO/IEC 18004:2015(E) -- 7.6 Constructing the final message codeword sequence (page 45)
    buff = make_final_message(version, error, buff)
    # Matrix with timing pattern and reserved format / version regions
    width = calc_matrix_size(version)
    height = width
    matrix = make_matrix(width, height)
    # ISO/IEC 18004:2015 -- 6.3.3 Finder pattern (page 16)
    add_finder_patterns(matrix, width, height)
    # ISO/IEC 18004:2015 -- 6.3.6 Alignment patterns (page 17)
    add_alignment_patterns(matrix, width, height)
    # ISO/IEC 18004:2015 -- 7.7 Codeword placement in matrix (page 46)
    add_codewords(matrix, buff, version)
    # ISO/IEC 18004:2015(E) -- 7.8.2 Data mask patterns (page 50)
    # ISO/IEC 18004:2015(E) -- 7.8.3 Evaluation of data masking results (page 53)
    mask, matrix = find_and_apply_best_mask(matrix, width, height, mask)
    # ISO/IEC 18004:2015(E) -- 7.9 Format information (page 55)
    add_format_info(matrix, version, error, mask)
    # ISO/IEC 18004:2015(E) -- 7.10 Version information (page 58)
    add_version_info(matrix, version)
    return Code(matrix, version, error, mask, segments)


def boost_error_level(version, error, segments, eci, is_sa=False):
    if error not in (consts.ERROR_LEVEL_H, None) and len(segments) == 1:
        levels = [consts.ERROR_LEVEL_L, consts.ERROR_LEVEL_M,
                  consts.ERROR_LEVEL_Q, consts.ERROR_LEVEL_H]
        if version < 1:
            levels.pop()  # H isn't support by Micro QR Codes
            if version < consts.VERSION_M4:
                levels.pop()  # Error level Q isn't supported by M2 and M3
        data_length = segments.bit_length_with_overhead(version, eci, is_sa=is_sa)
        for error_level in levels[levels.index(error) + 1:]:
            if consts.SYMBOL_CAPACITY[version][error_level] >= data_length:
                error = error_level
            else:
                break
    return error


def write_segment(buff, segment, ver, ver_range, eci=False):
    mode = segment.mode
    append_bits = buff.append_bits
    # Write ECI header if requested
    if eci and mode == consts.MODE_BYTE \
            and segment.encoding != consts.DEFAULT_BYTE_ENCODING:
        append_bits(consts.MODE_ECI, 4)
        append_bits(get_eci_assignment_number(segment.encoding), 8)
    if ver is None:  # QR Code
        append_bits(mode, 4)
        if mode == consts.MODE_HANZI:
            subset = 1  # Indicator for GB2312 subset
            append_bits(subset, 4)
    elif ver > consts.VERSION_M1:  # Micro QR Code (M1 has no mode indicator)
        append_bits(consts.MODE_TO_MICRO_MODE_MAPPING[mode], ver + 3)
    # Character count indicator
    append_bits(segment.char_count,
                consts.CHAR_COUNT_INDICATOR_LENGTH[mode][ver_range])
    buff.extend(segment.bits)


def write_terminator(buff, capacity, ver, length):
    buff.extend([0] * min(capacity - length, consts.TERMINATOR_LENGTH[ver]))


def write_padding_bits(buff, version, length):
    if version not in (consts.VERSION_M1, consts.VERSION_M3):
        buff.extend([0] * (8 - (length % 8)))


def write_pad_codewords(buff, version, capacity, length):
    write = buff.extend
    if version in (consts.VERSION_M1, consts.VERSION_M3):
        write([0] * (capacity - length))
    else:
        pad_codewords = ((1, 1, 1, 0, 1, 1, 0, 0), (0, 0, 0, 1, 0, 0, 0, 1))
        for i in range(capacity // 8 - length // 8):
            write(pad_codewords[i % 2])


# Finder pattern (includes separator around each side!)
_FINDER_PATTERN = ((0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0),
                   (0x0, 0x1, 0x1, 0x1, 0x1, 0x1, 0x1, 0x1, 0x0),
                   (0x0, 0x1, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0),
                   (0x0, 0x1, 0x0, 0x1, 0x1, 0x1, 0x0, 0x1, 0x0),
                   (0x0, 0x1, 0x0, 0x1, 0x1, 0x1, 0x0, 0x1, 0x0),
                   (0x0, 0x1, 0x0, 0x1, 0x1, 0x1, 0x0, 0x1, 0x0),
                   (0x0, 0x1, 0x0, 0x0, 0x0, 0x0, 0x0, 0x1, 0x0),
                   (0x0, 0x1, 0x1, 0x1, 0x1, 0x1, 0x1, 0x1, 0x0),
                   (0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0))


def add_finder_patterns(matrix, width, height):
    is_square = width == height
    corners = ((0, 0), (0, len(matrix) - 8), (-8, 0))  # Upper left, upper right, bottom left
    if is_square and width < 21:
        corners = ((0, 0),)
    finder_range = range(8)
    for i, j in corners:
        offset = 1 if i == 0 else 0
        sepoffset = 0 if j != 0 else 1
        for r in finder_range:
            matrix[i + r][j:j + 8] = _FINDER_PATTERN[offset + r][sepoffset:sepoffset + 8]


def add_timing_pattern(matrix, is_micro):
    j, stop = (0, len(matrix)) if is_micro else (6, len(matrix) - 8)
    col = matrix[j]
    bit = 0x1
    for i in range(8, stop):
        matrix[i][j] = bit
        col[i] = bit
        bit ^= 0x1


def add_alignment_patterns(matrix, width, height):
    is_square = width == height
    version = (width - 17) // 4  # QR Codes: version * 4 +  17 == width / height of the matrix w/o border
    if is_square and version < 2:  # QR Codes version < 2 don't have alignment patterns
        return
    pattern = (0x1, 0x1, 0x1, 0x1, 0x1,
               0x1, 0x0, 0x0, 0x0, 0x1,
               0x1, 0x0, 0x1, 0x0, 0x1,
               0x1, 0x0, 0x0, 0x0, 0x1,
               0x1, 0x1, 0x1, 0x1, 0x1)
    positions = consts.ALIGNMENT_POS[version - 2]
    alignment_range = range(5)
    min_pos = positions[0]
    max_pos = positions[-1]
    finder_positions = ((min_pos, min_pos), (min_pos, max_pos), (max_pos, min_pos))
    for x, y in product(positions, repeat=2):
        if (x, y) in finder_positions:
            continue
        # The x and y values represent the center of the alignment pattern
        i, j = x - 2, y - 2
        for r in alignment_range:
            matrix[i + r][j:j + 5] = pattern[r * 5:r * 5 + 5]


def add_codewords(matrix, codewords, version):
    matrix_size = len(matrix)
    is_micro = version < 1
    # Necessary for M1 and M3: The algorithm would start at the upper right
    # corner, see <https://github.com/heuer/segno/issues/36>
    inc = 0 if version not in (consts.VERSION_M1, consts.VERSION_M3) else 2
    idx = 0  # Pointer to the current codeword
    codeword_length = len(codewords)
    range_two = range(2)
    for right in range(matrix_size - 1, 0, -2):
        if not is_micro and right <= 6:
            right -= 1
        for vertical in range(matrix_size):
            for z in range_two:
                j = right - z
                upwards = ((right + inc) & 2) == 0
                if not is_micro:
                    upwards ^= j < 6
                i = (matrix_size - 1 - vertical) if upwards else vertical
                row = matrix[i]
                if row[j] == 0x2 and idx < codeword_length:
                    row[j] = codewords[idx]
                    idx += 1
    if idx != len(codewords):  # pragma: no cover
        raise ValueError('Internal error: Adding codewords to matrix failed. '
                         f'Added {idx} of {len(codewords)} codewords')


def make_final_message(version, error, buff):
    def to_binary(val, length=8):
        return ((val >> i) & 1 for i in reversed(range(length)))

    ec_infos = consts.ECC[version][error]
    data_blocks, error_blocks = make_blocks(ec_infos, buff)
    cw_four = None
    if version in (consts.VERSION_M1, consts.VERSION_M3):
        cw_four = to_binary(data_blocks[0].pop(-1) >> 4, 4)
    res = Buffer()
    # Write codewords
    res.extend(chain(*map(to_binary, (x for x in chain.from_iterable(zip_longest(*data_blocks)) if x is not None))))
    if cw_four is not None:
        res.extend(cw_four)
    # Write error codewords
    res.extend(chain(*map(to_binary, (x for x in chain.from_iterable(zip_longest(*error_blocks)) if x is not None))))
    remainder = 0
    if version in (2, 3, 4, 5, 6):
        remainder = 7
    elif version in (14, 15, 16, 17, 18, 19, 20, 28, 29, 30, 31, 32, 33, 34):
        remainder = 3
    elif version in (21, 22, 23, 24, 25, 26, 27):
        remainder = 4
    res.extend(b'\0' * remainder)
    return res


def make_blocks(ec_infos, buff):
    codewords = buff.toints()
    data_blocks, error_blocks = [], []
    append_data_block = data_blocks.append
    append_error_block = error_blocks.append
    gen_log = consts.GALIOS_LOG
    gen_exp = consts.GALIOS_EXP
    for ec_info in ec_infos:
        num_error_words = ec_info.num_total - ec_info.num_data
        gen = consts.GEN_POLY[num_error_words]
        range_error_words = range(num_error_words)
        for i in range(ec_info.num_blocks):
            block = bytearray(islice(codewords, ec_info.num_data))
            append_data_block(block)
            len_data = len(block)
            error_block = bytearray(block)
            error_block.extend([0] * num_error_words)
            # Extended synthetic division, see http://research.swtch.com/field
            for k in range(len_data):
                coef = error_block[k]
                if coef != 0:  # log(0) is undefined
                    lcoef = gen_log[coef]
                    for n in range_error_words:
                        error_block[k + n + 1] ^= gen_exp[lcoef + gen[n]]
            append_error_block(error_block[len_data:])
    return data_blocks, error_blocks


def find_and_apply_best_mask(matrix, width, height, proposed_mask=None):
    is_better = lt
    best_score = _MAX_PENALTY_SCORE
    eval_mask = evaluate_mask
    is_micro = width == height and width < 21
    if is_micro:
        is_better = gt
        best_score = -1
        eval_mask = evaluate_micro_mask
    # Matrix to check if a module belongs to the encoding region
    # or to the function patterns
    function_matrix = make_matrix(width, height)
    add_finder_patterns(function_matrix, width, height)
    add_alignment_patterns(function_matrix, width, height)
    if not is_micro:
        function_matrix[-8][8] = 0x1

    def is_encoding_region(i, j):
        return function_matrix[i][j] > 0x1

    mask_patterns = get_data_mask_functions(is_micro)
    # If the user supplied a mask pattern, the evaluation step is skipped
    if proposed_mask is not None:
        apply_mask(matrix, mask_patterns[proposed_mask], width, height,
                   is_encoding_region)
        return proposed_mask, matrix

    best_matrix = None
    for mask_number, mask_pattern in enumerate(mask_patterns):
        m = [ba[:] for ba in matrix]
        apply_mask(m, mask_pattern, width, height, is_encoding_region)
        # NOTE: DO NOT add format / version info in advance of evaluation
        # See ISO/IEC 18004:2015(E) -- 7.8. Data masking (page 50)
        score = eval_mask(m, width, height)
        if is_better(score, best_score):
            best_score = score
            best_pattern = mask_number
            best_matrix = tuple(m)
    return best_pattern, best_matrix


def apply_mask(matrix, mask_pattern, width, height, is_encoding_region):
    width_range = range(width)
    for i in range(height):
        row = matrix[i]
        for j in width_range:
            if is_encoding_region(i, j):
                row[j] ^= mask_pattern(i, j)


def evaluate_mask(matrix, width, height):
    return sum(mask_scores(matrix, width, height))


def mask_scores(matrix, width, height):
    n3_pattern = bytearray((0x1, 0x0, 0x1, 0x1, 0x1, 0x0, 0x1))

    def n3_pattern_occurrences(seq):
        count = 0
        idx = seq.find(n3_pattern)
        while idx != -1:
            offset = idx + 7
            if idx in (0, qr_size - 7) \
                    or not any(seq[max(idx - 4, 0):min(idx, qr_size)]) \
                    or not any(seq[max(offset, 0):min(offset + 4, qr_size)]):
                count += 40  # N3 = 40
            else:
                offset = idx + 4
            idx = seq.find(n3_pattern, offset)
        return count

    score_n1 = 0
    score_n2 = 0
    score_n3 = 0
    assert width == height
    qr_size = width
    qr_module_range = range(qr_size)
    dark_module_counter = 0
    last_row = None
    # Collects the bytes column-wise (required to calculate score N3)
    n3_column = bytearray(qr_size)
    for i in qr_module_range:
        row = matrix[i]
        row_prev_bit = -1
        col_prev_bit = -1
        # N1
        n1_row_counter = 0
        n1_col_counter = 0
        for j in qr_module_range:
            row_current_bit = row[j]
            col_current_bit = matrix[j][i]
            n3_column[j] = col_current_bit
            dark_module_counter += row_current_bit
            # N1 -- row-wise
            if row_current_bit == row_prev_bit:
                n1_row_counter += 1
            else:
                if n1_row_counter >= 5:
                    score_n1 += n1_row_counter - 2
                n1_row_counter = 1
            # N1 -- col-wise
            if col_current_bit == col_prev_bit:
                n1_col_counter += 1
            else:
                if n1_col_counter >= 5:
                    score_n1 += n1_col_counter - 2
                n1_col_counter = 1
            # N2
            if last_row and j and row_current_bit == row_prev_bit == last_row[j] == last_row[j - 1]:
                score_n2 += 3
            row_prev_bit = row_current_bit
            col_prev_bit = col_current_bit
        last_row = row
        # N3
        score_n3 += n3_pattern_occurrences(row)
        score_n3 += n3_pattern_occurrences(n3_column)
        # N1
        if n1_row_counter >= 5:
            score_n1 += n1_row_counter - 2
        if n1_col_counter >= 5:
            score_n1 += n1_col_counter - 2
    # N4
    percent = float(dark_module_counter) / (qr_size ** 2)
    score_n4 = 10 * int(abs(percent * 100 - 50) / 5)  # N4 = 10
    return score_n1, score_n2, score_n3, score_n4


def evaluate_micro_mask(matrix, width, height):
    module_range = range(1, width)
    last_row = matrix[-1]
    sum1 = sum(matrix[i][-1] for i in module_range)
    sum2 = sum(last_row[i] for i in module_range)
    return sum1 * 16 + sum2 if sum1 <= sum2 else sum2 * 16 + sum1


def calc_format_info(version, error, mask_pattern):
    fmt = mask_pattern
    if version > 0:
        if error == consts.ERROR_LEVEL_L:
            fmt += 0x08
        elif error == consts.ERROR_LEVEL_H:
            fmt += 0x10
        elif error == consts.ERROR_LEVEL_Q:
            fmt += 0x18
        format_info = consts.FORMAT_INFO[fmt]
    else:
        fmt += consts.ERROR_LEVEL_TO_MICRO_MAPPING[version][error] << 2
        format_info = consts.FORMAT_INFO_MICRO[fmt]
    return format_info


def add_format_info(matrix, version, error, mask_pattern):
    is_micro = version < 1
    format_info = calc_format_info(version, error, mask_pattern)
    voffset = int(is_micro)
    hoffset = voffset
    row_eight = matrix[8]
    for i in range(8):
        vbit = (format_info >> i) & 0x01
        hbit = (format_info >> (14 - i)) & 0x01
        if i == 6 and not is_micro:  # Timing pattern
            voffset += 1
            hoffset = 1
        # vertical row, upper left corner
        matrix[i + voffset][8] = vbit
        # horizontal row, upper left corner
        row_eight[i + hoffset] = hbit
        if not is_micro:
            # horizontal row, upper right corner
            row_eight[-1 - i] = vbit
            # vertical row, bottom left corner
            matrix[-1 - i][8] = hbit
    if not is_micro:
        # Dark module
        matrix[-8][8] = 0x1


def add_version_info(matrix, version):
    if version < 7:
        return
    version_info = consts.VERSION_INFO[version - 7]
    for i in range(6):
        bit1 = (version_info >> (i * 3)) & 0x01
        bit2 = (version_info >> ((i * 3) + 1)) & 0x01
        bit3 = (version_info >> ((i * 3) + 2)) & 0x01
        # Lower left
        matrix[-11][i] = bit1
        matrix[-10][i] = bit2
        matrix[-9][i] = bit3
        # Upper right
        row = matrix[i]
        row[-11] = bit1
        row[-10] = bit2
        row[-9] = bit3


def prepare_data(content, mode, encoding):
    segments = Segments()
    add_segment = segments.add_segment
    if isinstance(content, (str, bytes, int)):
        add_segment(make_segment(content, mode, encoding))
        return segments
    for item in content:
        seg_content, seg_mode, seg_encoding = item, mode, encoding
        if isinstance(item, tuple):
            seg_content = item[0]
            if len(item) > 1:
                seg_mode = item[1] or mode  # item[1] could be None
            if len(item) > 2:
                seg_encoding = item[2] or encoding  # item[2] may be None
        add_segment(make_segment(seg_content, seg_mode, seg_encoding))
    return segments


def data_to_bytes(data, encoding):
    if isinstance(data, bytes):
        return data, len(data), encoding or consts.DEFAULT_BYTE_ENCODING
    data = str(data)
    if encoding is not None:
        # Use the provided encoding; could raise an exception by intention
        data = data.encode(encoding)
    else:
        try:
            # Try to use the default byte encoding
            encoding = consts.DEFAULT_BYTE_ENCODING
            data = data.encode(encoding)
        except UnicodeError:
            try:
                # Try Kanji / Shift_JIS
                encoding = consts.KANJI_ENCODING
                data = data.encode(encoding)
            except UnicodeError:
                # Use UTF-8
                encoding = 'utf-8'
                data = data.encode(encoding)
    return data, len(data), encoding


def make_segment(data, mode, encoding=None):
    if mode == consts.MODE_HANZI:
        encoding = consts.HANZI_ENCODING
    segment_data, segment_length, segment_encoding = data_to_bytes(data, encoding)
    segment_mode = mode
    guessed_mode = find_mode(segment_data) if segment_mode != consts.MODE_BYTE else consts.MODE_BYTE
    if segment_mode is not None:
        # Check if user provided mode is applicable for the given segment_data
        if segment_mode < guessed_mode:
            raise ValueError(f'The provided mode "{get_mode_name(segment_mode)}" '
                             f'is not applicable for {segment_data!r}. '
                             f'Proposal: {get_mode_name(guessed_mode)}')
    else:
        segment_mode = guessed_mode
    if segment_mode != consts.MODE_BYTE:
        segment_encoding = None
    char_count = segment_length if segment_mode not in (consts.MODE_KANJI, consts.MODE_HANZI) else segment_length // 2
    buff = Buffer()
    append_bits = buff.append_bits
    if segment_mode == consts.MODE_NUMERIC:
        for i in range(0, segment_length, 3):
            chunk = segment_data[i:i + 3]
            append_bits(int(chunk), len(chunk) * 3 + 1)
    elif segment_mode == consts.MODE_ALPHANUMERIC:
        # ISO/IEC 18004:2015(E) -- 7.4.4 Alphanumeric mode (page 26)
        to_byte = consts.ALPHANUMERIC_CHARS.find
        for i in range(0, segment_length, 2):
            chunk = segment_data[i:i + 2]
            if len(chunk) > 1:
                append_bits(to_byte(chunk[0]) * 45 + to_byte(chunk[1]), 11)
            else:
                append_bits(to_byte(chunk), 6)
    elif segment_mode == consts.MODE_BYTE:
        # ISO/IEC 18004:2015(E) -- 7.4.5 Byte mode (page 27)
        for b in segment_data:
            append_bits(b, 8)
    elif segment_mode == consts.MODE_HANZI:
        # GBT 18284-2000 -- 6.4.5 Hanzi mode (page 18)
        # Note: len(segment.data)! segment.data_length = len(segment.data) / 2!!
        for i in range(0, segment_length, 2):
            code = (segment_data[i] << 8) | segment_data[i + 1]
            if 0xa1a1 <= code <= 0xaafe:
                # For characters with GB2312 values from A1A1HEX to AAFEHEX:
                # a) Subtract A1A1HEX from GB2312 value;
                diff = code - 0xa1a1
            elif 0xb0a1 <= code <= 0xfafe:
                # For characters with GB2312 values from B0A1HEX to FAFEHEX:
                # a) Subtract A6A1HEX from GB2312 value;
                diff = code - 0xa6a1
            else:  # pragma: no cover
                raise ValueError(f'Invalid Hanzi bytes: {code}')
            append_bits(((diff >> 8) * 0x60) + (diff & 0xff), 13)
    else:
        # ISO/IEC 18004:2015(E) -- 7.4.6 Kanji mode (page 29)
        for i in range(0, segment_length, 2):
            code = (segment_data[i] << 8) | segment_data[i + 1]
            if 0x8140 <= code <= 0x9ffc:
                # 1. a) For characters with Shift JIS values from 8140HEX to 9FFCHEX:
                # Subtract 8140HEX from Shift JIS value;
                diff = code - 0x8140
            elif 0xe040 <= code <= 0xebbf:
                # 2. a) For characters with Shift JIS values from E040HEX to EBBFHEX:
                # Subtract C140HEX from Shift JIS value;
                diff = code - 0xc140
            else:  # pragma: no cover
                raise ValueError(f'Invalid Kanji bytes: {code}')
            append_bits(((diff >> 8) * 0xc0) + (diff & 0xff), 13)
    return _Segment(buff.getbits(), char_count, segment_mode, segment_encoding)


def make_matrix(width, height, reserve_regions=True, add_timing=True):
    is_square = width == height
    is_micro = is_square and width < 21
    row = [0x2] * width
    matrix = tuple(bytearray(row) for i in range(height))
    if reserve_regions:
        if is_square and width > 41:  # QR Codes < version 7 don't have a version pattern
            # Reserve version pattern areas
            for i in range(6):
                row = matrix[i]
                # Upper right
                row[-11] = 0x0
                row[-10] = 0x0
                row[-9] = 0x0
                # Lower left
                matrix[-11][i] = 0x0
                matrix[-10][i] = 0x0
                matrix[-9][i] = 0x0
        # Reserve format pattern areas
        row_eight = matrix[8]
        for i in range(9):
            matrix[i][8] = 0x0  # Upper left
            row_eight[i] = 0x0  # Upper bottom
            if not is_micro:
                matrix[-i][8] = 0x0  # Bottom left
                row_eight[-i] = 0x0  # Upper right
    if add_timing:
        # ISO/IEC 18004:2015 -- 6.3.5 Timing pattern (page 17)
        add_timing_pattern(matrix, is_micro)
    return matrix


def normalize_version(version):
    if version is None:
        return None
    error = False
    try:
        version = int(version)
        # Don't want Micro QR Code constants as input
        error = version < 1
    except (ValueError, TypeError):
        try:
            version = consts.MICRO_VERSION_MAPPING[version.upper()]
        except (KeyError, AttributeError):
            error = True
    if error or (not 0 < version < 41 and version not in consts.MICRO_VERSIONS):
        raise ValueError(f'Unsupported version "{version}". '
                         f'Supported: {", ".join(sorted(consts.MICRO_VERSION_MAPPING.keys()))} and 1 .. 40')
    return version


def normalize_mode(mode):
    if mode is None or mode in consts.MODE_MAPPING.values():
        return mode
    try:
        return consts.MODE_MAPPING[mode.lower()]
    except (KeyError, AttributeError):
        raise ValueError(f'Illegal mode "{mode}". '
                         f'Supported values: {", ".join(sorted(consts.MODE_MAPPING.keys()))}')


def normalize_mask(mask, is_micro):
    if mask is None:
        return None
    try:
        mask = int(mask)
    except ValueError:
        raise ValueError(f'Invalid data mask "{mask}". '
                         'Must be an integer or a string which represents an integer value.')
    if is_micro:
        if not 0 <= mask < 4:
            raise ValueError(f'Invalid data mask "{mask}" for Micro QR Code. Must be in range 0 .. 3')
    else:
        if not 0 <= mask < 8:
            raise ValueError(f'Invalid data mask "{mask}". Must be in range 0 .. 7')
    return mask


def normalize_errorlevel(error, accept_none=False):
    if error is None:
        if not accept_none:
            raise ValueError('The error level must be provided')
        return error
    try:
        return consts.ERROR_MAPPING[error.upper()]
    except (KeyError, AttributeError):
        if error in consts.ERROR_MAPPING.values():
            return error
        raise ValueError(f'Illegal error correction level: "{error}". Supported levels: L, M, Q, H')


def get_mode_name(mode_const):
    for name, val in consts.MODE_MAPPING.items():
        if val == mode_const:
            return name
    raise ValueError(f'Unknown mode "{mode_const}"')


def get_error_name(error_const):
    for name, val in consts.ERROR_MAPPING.items():
        if val == error_const:
            return name
    raise ValueError(f'Unknown error level "{error_const}"')


def get_version_name(version_const):
    if 0 < version_const < 41:
        return version_const
    for name, v in consts.MICRO_VERSION_MAPPING.items():
        if v == version_const:
            return name
    raise ValueError(f'Unknown version constant "{version_const}"')


_ALPHANUMERIC_PATTERN = re.compile(br'^[' + re.escape(consts.ALPHANUMERIC_CHARS) + br']+\Z')


def is_alphanumeric(data):
    return _ALPHANUMERIC_PATTERN.match(data)


def is_kanji(data):
    data_len = len(data)
    if not data_len or data_len % 2:
        return False
    data_iter = iter(data)
    for i in range(0, data_len, 2):
        code = (next(data_iter) << 8) | next(data_iter)
        if not (0x8140 <= code <= 0x9ffc or 0xe040 <= code <= 0xebbf):
            return False
    return True


def find_mode(data):
    if data.isdigit():
        return consts.MODE_NUMERIC
    if is_alphanumeric(data):
        return consts.MODE_ALPHANUMERIC
    if is_kanji(data):
        return consts.MODE_KANJI
    return consts.MODE_BYTE


def find_version(segments, error, eci, micro, is_sa=False):
    assert not (eci and micro)
    micro_allowed = micro or micro is None
    min_version = consts.VERSION_M1 if micro_allowed else 1
    max_version = consts.VERSION_M4 if micro else 40
    if min_version < 1:
        min_version = max([find_minimum_version_for_mode(mode) for mode in segments.modes])
    if error is not None and micro_allowed:
        min_version = consts.VERSION_M2
    for version in range(min_version, max_version + 1):
        if error is None and version != consts.VERSION_M1:
            error = consts.ERROR_LEVEL_L
        try:
            if consts.SYMBOL_CAPACITY[version][error] >= segments.bit_length_with_overhead(version, eci, is_sa):
                return version
        except KeyError:
            pass
    help_txt = ''
    if micro is None:
        help_txt = '(Micro) '
    elif micro:
        help_txt = 'Micro '
    raise DataOverflowError(f'Data too large. No {help_txt}QR Code can handle the provided data')


def calc_matrix_size(ver):
    return ver * 4 + 17 if ver > 0 else (ver + 4) * 2 + 9


def calc_structured_append_parity(content):
    if not isinstance(content, str):
        content = str(content)
    try:
        data = content.encode('iso-8859-1')
    except UnicodeError:
        try:
            data = content.encode('shift-jis')
        except (LookupError, UnicodeError):
            data = content.encode('utf-8')
    return reduce(xor, data)


def is_mode_supported(mode, ver):
    ver = None if ver > 0 else ver
    try:
        return ver in consts.SUPPORTED_MODES[mode]
    except KeyError:
        raise ValueError(f'Unknown mode "{mode}"')


def find_minimum_version_for_mode(mode):
    for v in consts.MICRO_VERSIONS:
        if is_mode_supported(mode, v):
            return v
    return 1


def version_range(version):
    if 0 < version < 10:
        return consts.VERSION_RANGE_01_09
    elif 9 < version < 27:
        return consts.VERSION_RANGE_10_26
    elif 26 < version < 41:
        return consts.VERSION_RANGE_27_40
    raise ValueError(f'Unknown version "{version}"')


def get_eci_assignment_number(encoding):
    try:
        return consts.ECI_ASSIGNMENT_NUM[codecs.lookup(encoding).name]
    except KeyError:
        raise ValueError(f'Unknown ECI assignment number for encoding "{encoding}".')


def get_data_mask_functions(is_micro):
    def fn0(i, j):
        return (i + j) & 0x1 == 0

    def fn1(i, j):
        return i & 0x1 == 0

    def fn2(i, j):
        return j % 3 == 0

    def fn3(i, j):
        return (i + j) % 3 == 0

    def fn4(i, j):
        return (i // 2 + j // 3) & 0x1 == 0

    def fn5(i, j):
        tmp = i * j
        return (tmp & 0x1) + (tmp % 3) == 0

    def fn6(i, j):
        tmp = i * j
        return ((tmp & 0x1) + (tmp % 3)) & 0x1 == 0

    def fn7(i, j):
        return (((i + j) & 0x1) + (i * j) % 3) & 0x1 == 0

    if is_micro:
        return fn1, fn4, fn6, fn7
    return fn0, fn1, fn2, fn3, fn4, fn5, fn6, fn7


class Segments:
    __slots__ = ('bit_length', 'modes', 'segments')

    def __init__(self):
        self.segments = []
        self.bit_length = 0
        self.modes = []

    def add_segment(self, segment):
        """\

        :param _Segment segment: Segment to add.
        """
        if self.segments:
            prev_seg = self.segments[-1]
            if prev_seg.mode == segment.mode and prev_seg.encoding == segment.encoding:
                # Merge segment with previous segment
                segment = _Segment(prev_seg.bits + segment.bits,
                                   prev_seg.char_count + segment.char_count,
                                   segment.mode, segment.encoding)
                self.bit_length -= len(prev_seg.bits)
                del self.segments[-1]
                del self.modes[-1]
        self.segments.append(segment)
        self.bit_length += len(segment.bits)
        self.modes.append(segment.mode)

    def __len__(self):
        return len(self.segments)

    def __getitem__(self, item):
        return self.segments[item]

    def __iter__(self):
        return iter(self.segments)

    def bit_length_with_overhead(self, version, eci, is_sa=False):
        overhead = 0
        # ECI overhead
        if eci:
            no_eci_indicators = sum(1 for segment in self.segments
                                    if segment.mode == consts.MODE_BYTE
                                    and segment.encoding != consts.DEFAULT_BYTE_ENCODING)
            overhead += no_eci_indicators * 4  # ECI indicator
            overhead += no_eci_indicators * 8  # ECI assignment no
        if is_sa:
            # 4 bit for mode, 4 bit for the position, 4 bit for total number of symbols
            # 8 bit for parity data
            overhead += 5 * 4
        # Mode indicator overhead
        if version > 0:  # QR Code
            overhead += len(self.modes) * 4
        elif version > consts.VERSION_M1:  # Micro QR Code (M1 has no mode indicator)
            overhead += len(self.modes) * (version + 3)
        # Char count indicator overhead
        ver_range = version_range(version) if version > 0 else version
        overhead += sum(consts.CHAR_COUNT_INDICATOR_LENGTH[mode][ver_range] for mode in self.modes)
        return overhead + self.bit_length


class _Segment(tuple):
    __slots__ = ()

    def __new__(cls, bits, char_count, mode, encoding=None):
        return tuple.__new__(cls, (bits, char_count, mode, encoding))

    bits = property(itemgetter(0))
    char_count = property(itemgetter(1))
    mode = property(itemgetter(2))
    encoding = property(itemgetter(3))


class Buffer:
    __slots__ = ['_data']

    def __init__(self, iterable=()):
        self._data = bytearray(iterable)

    def extend(self, iterable):
        self._data.extend(iterable)

    def append_bits(self, val, length):
        self._data.extend((val >> i) & 1 for i in reversed(range(length)))

    def getbits(self):
        return self._data

    def toints(self):
        """\
        Returns an iterable of integers interpreting the content of `seq`
        as sequence of binary numbers of length 8.
        """
        return (int(''.join(map(str, g)), 2) for g in zip_longest(*[iter(self._data)] * 8, fillvalue=0))

    def __len__(self):
        return len(self._data)

    def __getitem__(self, item):
        return self._data[item]


class _StructuredAppendInfo(tuple):
    __slots__ = ()

    def __new__(cls, number, total, parity):
        return super().__new__(cls, (consts.MODE_STRUCTURED_APPEND, number, total, parity))

    mode = property(itemgetter(0))
    number = property(itemgetter(1))
    total = property(itemgetter(2))
    parity = property(itemgetter(3))
