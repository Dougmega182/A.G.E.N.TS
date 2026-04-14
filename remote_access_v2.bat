@echo off
echo ==================================================
echo  A.G.E.N.T.S. REMOTE ACCESS (PINGGY)
echo ==================================================
echo.
echo [1/2] Connecting to high-reliability tunnel...
echo.
echo - Copy the 'https' URL that appears below.
echo - Keep this window OPEN while on your phone.
echo --------------------------------------------------
ssh -p 443 -o StrictHostKeyChecking=no -R0:localhost:8000 +@a.pinggy.io
echo --------------------------------------------------
pause
