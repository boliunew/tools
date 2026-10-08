@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -c "import libtorrent" 2>nul || (echo 第一次用，先装 libtorrent... & python -m pip install libtorrent)
python torrent_hub.py --lan %*
pause
