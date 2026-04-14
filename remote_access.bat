@echo off
echo ==================================================
echo  A.G.E.N.T.S. REMOTE ACCESS TUNNEL
echo ==================================================
echo.
echo [1/2] Connecting to secure tunnel via localhost.run...
echo.
echo IMPORTANT: 
echo - Copy the 'https' URL that appears below.
echo - Keep this window OPEN while using your phone.
echo - Press Ctrl+C to stop remote access.
echo.
echo --------------------------------------------------
ssh -R 80:localhost:8000 nokey@localhost.run
echo --------------------------------------------------
pause
