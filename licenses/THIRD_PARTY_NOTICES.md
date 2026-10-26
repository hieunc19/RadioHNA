# Third-party components to include in the release package

This source tree does not redistribute model weights, Tesseract binaries,
`vie.traineddata`, or FFmpeg binaries. Before releasing `PHÁT THANH AI`, copy
the license/NOTICE files from the exact versions placed in the one-folder
bundle into this `licenses/` directory.

| Component | Use in this project | License / notice source to include |
| --- | --- | --- |
| VieNeu-TTS / `vieneu` | Offline Vietnamese text-to-speech SDK | VieNeu-TTS repository `LICENSE` (Apache-2.0); also verify terms for the exact model and preset-voice assets used. |
| Tesseract OCR | Local OCR engine | Tesseract distribution `LICENSE` / `COPYING`. |
| `vie.traineddata` | Vietnamese OCR language data | License distributed with the selected tessdata source. |
| PaddleOCR / PaddlePaddle | Offline text-line detection on CPU | Apache-2.0 license and notices from the exact installed distributions and model cards. |
| VietOCR | Offline Vietnamese text-line recognition | VietOCR repository/license and the notice for the exact `vgg_seq2seq` weights. |
| PyTorch / TorchVision | VietOCR CPU runtime | BSD-style license and notices from the installed distributions. |
| OpenCV | Perspective crop of detected text lines | Apache-2.0 license and notices from the installed distribution. |
| FFmpeg | Local WAV concat and MP3 encoding | Notices and licenses for the exact FFmpeg build and enabled codecs. |
| FastAPI / Starlette / Uvicorn | Loopback-only HTML/CSS/JavaScript web UI and local server | Licenses from the exact installed distributions. |
| python-multipart | Receive local browser file uploads | License from the installed distribution. |
| Pillow / pytesseract | Image preprocessing / Python OCR wrapper | Licenses from their installed distributions. |
| pypdf | Text extraction from text-layer PDFs | BSD-3-Clause license from the installed distribution. |
| pypdfium2 / PDFium | Render scanned-PDF pages for local OCR | License and PDFium dependency notices from the installed distribution. |
| PyInstaller | Windows one-folder build tool | PyInstaller GPL exception notice, if required by the release policy. |

Do not treat this checklist as legal advice. Record exact component versions and
review their redistribution conditions before copying the installer to a unit.
