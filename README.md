# 📌 الرصة | The Pinner

Clipboard manager — Windows / Mac / Linux

## Security Updates
Local data handling was hardened to validate imported content, write the user data file atomically, and clean up temporary clipboard files after use. The app now also handles malformed image and JSON content more safely.

## التشغيل
```bash
pip install -r requirements.txt
python main.py
```

## البناء كـ exe (Windows)
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "ThePinner" main.py
```

## License
This project is distributed under the MIT License. See [LICENSE](LICENSE) for the full text.

## البناء كـ app (Mac)
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "ThePinner" main.py
```
