Set WshShell = CreateObject("WScript.Shell")
exitCode = WshShell.Run("""E:\Projects\PDFStudio\app\scripts\start_pdfstudio.bat""", 0, True)
WScript.Quit exitCode
