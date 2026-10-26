# Third-Party Notices

FakeTyper V3 bundles third-party runtime components. This file lists the
principal components and their licenses; full license texts are in
`THIRD_PARTY_LICENSES/`.

The FakeTyper application itself is licensed under
[PolyForm Noncommercial License 1.0.0](LICENSE), not under the licenses below.

| Component | Version | License | Text |
|---|---|---|---|
| Python 3.13 | 3.13.13 | Python Software Foundation License | [python-3-13.txt](THIRD_PARTY_LICENSES/python-3-13.txt) |
| pywebview | 6.2.1 | BSD-3-Clause | [pywebview.txt](THIRD_PARTY_LICENSES/pywebview.txt) |
| pystray | 0.19.5 | LGPL-3.0 | [pystray.txt](THIRD_PARTY_LICENSES/pystray.txt) |
| Pillow | 12.2.0 | HPND | [pillow.txt](THIRD_PARTY_LICENSES/pillow.txt) |
| pythonnet | 3.2.1 | MIT | [pythonnet.txt](THIRD_PARTY_LICENSES/pythonnet.txt) |
| PyInstaller | 6.22.3 | GPL-2.0-or-later with bootloader exception | [pyinstaller.txt](THIRD_PARTY_LICENSES/pyinstaller.txt) |
| bottle | 0.13.4 | MIT | [bottle.txt](THIRD_PARTY_LICENSES/bottle.txt) |
| clr-loader | 0.3.1 | MIT | [clr-loader.txt](THIRD_PARTY_LICENSES/clr-loader.txt) |
| cffi | 2.1.1 | MIT | [cffi.txt](THIRD_PARTY_LICENSES/cffi.txt) |
| pycparser | 3.11 | BSD-3-Clause | [pycparser.txt](THIRD_PARTY_LICENSES/pycparser.txt) |
| typing_extensions | 4.16.0 | PSF-2.0 | [typing_extensions.txt](THIRD_PARTY_LICENSES/typing_extensions.txt) |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | [packaging.txt](THIRD_PARTY_LICENSES/packaging.txt) |
| React | 19.3.1 | MIT | [react.txt](THIRD_PARTY_LICENSES/react.txt) |
| React DOM | 19.3.1 | MIT | [react-dom.txt](THIRD_PARTY_LICENSES/react-dom.txt) |
| Radix UI | 1.8.1 | MIT | [radix-ui.txt](THIRD_PARTY_LICENSES/radix-ui.txt) |
| class-variance-authority | 0.7.1 | Apache-2.0 | [class-variance-authority.txt](THIRD_PARTY_LICENSES/class-variance-authority.txt) |
| clsx | 2.1.1 | MIT | [clsx.txt](THIRD_PARTY_LICENSES/clsx.txt) |
| tailwind-merge | 3.7.0 | MIT | [tailwind-merge.txt](THIRD_PARTY_LICENSES/tailwind-merge.txt) |
| Tailwind CSS | 4.3.3 | MIT | [tailwind-css.txt](THIRD_PARTY_LICENSES/tailwind-css.txt) |
| lucide-react | 1.61.0 | ISC | [lucide-react.txt](THIRD_PARTY_LICENSES/lucide-react.txt) |
| @fontsource-variable/geist | 5.3.0 | OFL-1.1 | [fontsource-variable-geist.txt](THIRD_PARTY_LICENSES/fontsource-variable-geist.txt) |
| tw-animate-css | 1.4.0 | MIT | [tw-animate-css.txt](THIRD_PARTY_LICENSES/tw-animate-css.txt) |
| @tailwindcss/vite | 4.3.3 | MIT | [tailwindcss-vite.txt](THIRD_PARTY_LICENSES/tailwindcss-vite.txt) |
| cn | 0.5.0 | MIT | [cn.txt](THIRD_PARTY_LICENSES/cn.txt) |

## Notes

- `Python 3.13` and the bundled standard library are distributed under the
  Python Software Foundation License.
- `PyInstaller` is used as the onefile bootloader. Its exception permits
  distributing bundled applications; the bootloader remains under its own
  license.
- `pystray` is LGPL-3.0; its license text is included. No modification is made
  to pystray in the released binary.
- `proxy-tools` (MIT) is a pywebview dependency without a license file in the
  installed metadata; see <https://pypi.org/project/proxy-tools/>.
- `Pillow` bundles several image codec libraries; their notices are included
  with the Pillow distribution and apply to the bundled DLLs.
- Microsoft Edge WebView2 Runtime is an operating-system component and is not
  bundled in `FakeTyper.exe`; it is required at runtime.
- Build-only JavaScript tooling (Vite, TypeScript, oxlint, Playwright, shadcn)
  is not shipped in the release archive and is not listed here.
