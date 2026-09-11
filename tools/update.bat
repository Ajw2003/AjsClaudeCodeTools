@echo off
REM ============================================================================
REM  update.bat - double-click this to update the house-rules plugin.
REM
REM  WHY A .BAT AND NOT JUST bootstrap.ps1: this is meant to be double-clicked
REM  from Explorer. PowerShell .ps1 files are not double-click-runnable by
REM  default - Windows opens them in an editor unless the execution policy and
REM  file association are both changed. A .bat runs on double-click on every
REM  Windows box with nothing configured.
REM
REM  WHY NO PYTHON: this file updates the plugin only. It runs the four claude
REM  CLI commands directly, so it needs no interpreter and no clone of this
REM  repo - copy it to your Desktop and it still works. If you also want the
REM  settings install.py applies - verbose, and model=opusplan for the CLI and
REM  IDE - run tools\bootstrap.ps1 instead, which needs Python and this repo.
REM
REM  WHY `call`: the claude CLI on Windows is claude.cmd. Running one .cmd from
REM  a .bat WITHOUT `call` hands control over and never comes back, so the
REM  script would stop dead after the first command. Every line below uses it.
REM
REM  The four commands and their order are not arbitrary - see install_steps()
REM  in tools/install.py, which holds the same sequence and carries the full
REM  reasoning. tools/verify_tools.py fails if the two ever disagree.
REM ============================================================================

setlocal
echo.
echo  house-rules - update
echo  ====================
echo.

where claude >nul 2>nul
if errorlevel 1 goto :noclaude

echo  [1 of 4] Declaring the marketplace - does nothing if already known
call claude plugin marketplace add https://github.com/Ajw2003/AjsClaudeCodeTools.git
if errorlevel 1 goto :failed
echo.

echo  [2 of 4] Refreshing the marketplace clone - this is the step that matters
call claude plugin marketplace update aj-house-rules
if errorlevel 1 goto :failed
echo.

echo  [3 of 4] Registering the plugin - does nothing if already installed
call claude plugin install house-rules@aj-house-rules -y
if errorlevel 1 goto :failed
echo.

echo  [4 of 4] Re-pointing the registration at the refreshed clone
call claude plugin update house-rules@aj-house-rules
if errorlevel 1 goto :failed
echo.

echo  ---------------------------------------------------------------
call claude plugin list
echo  ---------------------------------------------------------------
echo.
echo  DONE. Check the version above is the one you expected.
echo.
echo  Now FULLY QUIT Claude Code and start it again. Hooks and agents
echo  are read at startup, so nothing above is live in a window that
echo  is already open.
goto :done

:noclaude
echo  FAILED: claude is not on PATH, so nothing could be updated.
echo.
echo  Install Claude Code, then open a NEW window and run this again.
echo  A terminal opened before the install will not see it on PATH.
goto :done

:failed
echo.
echo  FAILED: the command above returned an error - its output says why.
echo.
echo  If it mentions the marketplace, check your network and try again.
echo  Nothing was left half-applied: re-running this file is safe.
goto :done

:done
echo.
pause
endlocal
