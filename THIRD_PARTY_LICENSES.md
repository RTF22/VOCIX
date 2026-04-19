# Third-Party Licenses

VOCIX is distributed as a portable Windows binary that bundles the Python runtime
and the dependencies listed below. Each component remains under its own license;
the notices required by MIT / BSD ("copyright notice and permission notice shall
be included in all copies or substantial portions of the Software") are reproduced
here.

VOCIX's own source code is covered by the [MIT License](LICENSE).

---

## Bundled Python dependencies

| Package | License | Project |
|---|---|---|
| faster-whisper | MIT | https://github.com/SYSTRAN/faster-whisper |
| ctranslate2 | MIT | https://github.com/OpenNMT/CTranslate2 |
| sounddevice | MIT | https://github.com/spatialaudio/python-sounddevice |
| numpy | BSD-3-Clause | https://numpy.org/ |
| keyboard | MIT | https://github.com/boppreh/keyboard |
| pyperclip | BSD-3-Clause | https://github.com/asweigart/pyperclip |
| pystray | LGPL-3.0 | https://github.com/moses-palmer/pystray |
| Pillow | MIT-CMU (HPND) | https://python-pillow.org/ |
| anthropic | MIT | https://github.com/anthropics/anthropic-sdk-python |
| python-dotenv | BSD-3-Clause | https://github.com/theskumar/python-dotenv |

> **Note on pystray (LGPL-3.0):** pystray is dynamically linked at runtime and is
> not modified by VOCIX. Users may replace the bundled pystray library with a
> compatible version. The full pystray source is available at the project URL
> above; a copy of LGPL-3.0 is reproduced at the end of this file.

The Whisper speech-to-text *model weights* are **not** bundled with VOCIX. They
are downloaded on first start from the Hugging Face model hub under the terms
chosen by the model publisher (typically MIT for `faster-whisper` / Systran).

## Whisper model weights

* Default model: `Systran/faster-whisper-small` (MIT) — https://huggingface.co/Systran/faster-whisper-small
* Alternative Whisper sizes: same license family

---

## License texts

### MIT License (applies to: faster-whisper, ctranslate2, sounddevice, keyboard, anthropic)

```
MIT License

Copyright (c) the respective authors of each project listed above.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### BSD 3-Clause License (applies to: numpy, pyperclip, python-dotenv)

```
Copyright (c) the respective authors of each project listed above.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
```

### HPND / MIT-CMU License (applies to: Pillow)

```
The Python Imaging Library (PIL) is

    Copyright © 1997-2011 by Secret Labs AB
    Copyright © 1995-2011 by Fredrik Lundh and contributors

Pillow is the friendly PIL fork. It is

    Copyright © 2010 by Jeffrey A. Clark and contributors

Like PIL, Pillow is licensed under the open source HPND License:

By obtaining, using, and/or copying this software and/or its associated
documentation, you agree that you have read, understood, and will comply
with the following terms and conditions:

Permission to use, copy, modify and distribute this software and its
documentation for any purpose and without fee is hereby granted, provided
that the above copyright notice appears in all copies, and that both that
copyright notice and this permission notice appear in supporting
documentation, and that the name of Secret Labs AB or the author not be
used in advertising or publicity pertaining to distribution of the software
without specific, written prior permission.

SECRET LABS AB AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS
SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS.
IN NO EVENT SHALL SECRET LABS AB OR THE AUTHOR BE LIABLE FOR ANY SPECIAL,
INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
```

### LGPL-3.0 (applies to: pystray)

The full text of the GNU Lesser General Public License v3.0 is available at
https://www.gnu.org/licenses/lgpl-3.0.txt and is incorporated here by reference.

Key obligations for downstream distributors of VOCIX:

1. Keep this notice and the reference to the pystray project source.
2. Allow users to replace the pystray library in the distribution (the VOCIX
   portable folder contains pystray as a separate set of .pyd/.py files, which
   satisfies this requirement).
3. Provide the pystray source on request; upstream sources remain available at
   https://github.com/moses-palmer/pystray.

---

## Assets

* VOCIX logo, icon set and landing-page artwork: © 2026 Jens Fricke / RTF22,
  all rights reserved; redistributed under the project's MIT License for use
  together with VOCIX.
