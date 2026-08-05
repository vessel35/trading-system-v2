# Third-Party Notices

## TA-Lib

This repository contains direct Python ports of TA-Lib v0.7.1 candlestick
calculation logic under `services/core-lib/core_lib/patterns/talib_*.py`.
The corresponding unmodified C sources and the pinned sources for the planned
Hilbert indicator ports are vendored under `third_party/ta-lib/` with their
original path structure. The snapshot contains `src/ta_common/ta_global.c`,
`src/ta_func/ta_utility.h`, the 61 `src/ta_func/ta_CDL*.c` files, and the seven
indicator files `ta_HT_DCPERIOD.c`, `ta_HT_DCPHASE.c`, `ta_HT_PHASOR.c`,
`ta_HT_SINE.c`, `ta_HT_TRENDLINE.c`, `ta_HT_TRENDMODE.c`, and `ta_MAMA.c` under
`src/ta_func/`. The upstream `LICENSE` is preserved alongside the snapshot.

TA-Lib license and copyright notice:

Copyright (c) 1999-2025, Mario Fortier

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
