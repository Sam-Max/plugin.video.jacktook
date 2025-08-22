#
# Copyright (c) 2016 - 2024 -- Lars Heuer
# All rights reserved.
#
# License: BSD License
#
"""\
QR Code and Micro QR Code implementation.

"QR Code" and "Micro QR Code" are registered trademarks of DENSO WAVE INCORPORATED.
"""
import sys
import io
from . import encoder
from .encoder import DataOverflowError
from . import writers, utils

__version__ = '1.6.6'

__all__ = ('make', 'make_qr', 'make_micro', 'make_sequence', 'QRCode',
           'QRCodeSequence', 'DataOverflowError')


def make(content, error=None, version=None, mode=None, mask=None, encoding=None,
         eci=False, micro=None, boost_error=True):
    return QRCode(encoder.encode(content, error, version, mode, mask, encoding,
                                 eci, micro, boost_error=boost_error))



class QRCode:
    __slots__ = ('_error', '_matrix_size', '_mode', '_version', 'mask', 'matrix')

    def __init__(self, code):
        matrix = code.matrix
        self.matrix = matrix
        self.mask = code.mask
        self._matrix_size = len(matrix[0]), len(matrix)
        self._version = code.version
        self._error = code.error
        self._mode = code.segments[0].mode if len(code.segments) == 1 else None

    @property
    def version(self):
        return encoder.get_version_name(self._version)

    @property
    def error(self):
        if self._error is None:
            return None
        return encoder.get_error_name(self._error)

    @property
    def mode(self):
        if self._mode is not None:
            return encoder.get_mode_name(self._mode)
        return None

    @property
    def designator(self):
        version = str(self.version)
        return '-'.join((version, self.error) if self.error else (version,))

    @property
    def default_border_size(self):
        return utils.get_default_border_size(self._matrix_size)

    @property
    def is_micro(self):
        return self._version < 1

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.matrix == other.matrix

    __hash__ = None

    def symbol_size(self, scale=1, border=None):
        return utils.get_symbol_size(self._matrix_size, scale=scale, border=border)

    def matrix_iter(self, scale=1, border=None, verbose=False):
        iterfn = utils.matrix_iter_verbose if verbose else utils.matrix_iter
        return iterfn(self.matrix, self._matrix_size, scale, border)

    def show(self, delete_after=20, scale=10, border=None, dark='#000',
             light='#fff'):  # pragma: no cover
        import os
        import time
        import tempfile
        import webbrowser
        import threading
        from urllib.parse import urljoin
        from urllib.request import pathname2url

        def delete_file(name):
            time.sleep(delete_after)
            try:
                os.unlink(name)
            except OSError:
                pass

        f = tempfile.NamedTemporaryFile('wb', suffix='.png', delete=False)
        try:
            self.save(f, scale=scale, dark=dark, light=light, border=border)
        except:
            f.close()
            os.unlink(f.name)
            raise
        f.close()
        webbrowser.open_new_tab(urljoin('file:', pathname2url(f.name)))
        if delete_after is not None:
            t = threading.Thread(target=delete_file, args=(f.name,))
            t.start()

    def svg_data_uri(self, xmldecl=False, encode_minimal=False,
                     omit_charset=False, nl=False, **kw):
        return writers.as_svg_data_uri(self.matrix, self._matrix_size,
                                       xmldecl=xmldecl, nl=nl,
                                       encode_minimal=encode_minimal,
                                       omit_charset=omit_charset, **kw)

    def svg_inline(self, **kw):
        buff = io.BytesIO()
        self.save(buff, kind='svg', xmldecl=False, svgns=False, nl=False, **kw)
        return buff.getvalue().decode(kw.get('encoding', 'utf-8'))

    def png_data_uri(self, **kw):
        return writers.as_png_data_uri(self.matrix, self._matrix_size, **kw)

    def terminal(self, out=None, border=None, compact=False):
        if compact:
            writers.write_terminal_compact(self.matrix, self._matrix_size, out or sys.stdout, border)
        elif out is None and sys.platform == 'win32':  # pragma: no cover
            try:
                writers.write_terminal_win(self.matrix, self._matrix_size, border)
            except OSError:
                writers.write_terminal(self.matrix, self._matrix_size, sys.stdout, border)
        else:
            writers.write_terminal(self.matrix, self._matrix_size, out or sys.stdout, border)

    def save(self, out, kind=None, **kw):
        writers.save(self.matrix, self._matrix_size, out, kind, **kw)

    def __getattr__(self, name):
        if name.startswith('to_'):
            try:
                import importlib_metadata as metadata
            except ImportError:
                from importlib import metadata
            from functools import partial
            for ep in metadata.entry_points(group='segno.plugin.converter',
                                            name=name[3:]):
                plugin = ep.load()
                return partial(plugin, self)
        raise AttributeError(f'{self.__class__} object has no attribute {name}')


class QRCodeSequence(tuple):
    __slots__ = ()

    def __new__(cls, qrcodes):
        return super().__new__(cls, qrcodes)

    def terminal(self, out=None, border=None, compact=False):
        for qrcode in self:
            qrcode.terminal(out=out, border=border, compact=compact)

    def save(self, out, kind=None, **kw):
        filename = lambda o, n: o  # noqa: E731
        m = len(self)
        if m > 1 and isinstance(out, str):
            dot_idx = out.rfind('.')
            if dot_idx > -1:
                out = out[:dot_idx] + '-{0:02d}-{1:02d}' + out[dot_idx:]
                filename = lambda o, n: o.format(m, n)  # noqa: E731
        for n, qrcode in enumerate(self, start=1):
            qrcode.save(filename(out, n), kind=kind, **kw)

    def __getattr__(self, item):
        if len(self) == 1:
            return getattr(self[0], item)
        raise AttributeError(f"{self.__class__} object has no attribute '{item}'")
