# Install a Development Package from ZIP

The ZIP contains the complete repository contents but intentionally excludes `.git`, `.venv`, generated caches, and Finder metadata.

1. Close the IrrigationOS workspace in VS Code.
2. In Finder, open `/Users/davidbuch/Documents/GitHub/IrrigationOS`.
3. Preserve the existing hidden `.git` folder.
4. Delete the repository contents except `.git` and `.venv`.
5. Extract the release ZIP.
6. Press **Command + Shift + .** in Finder so hidden files are visible.
7. Copy everything inside the extracted `IrrigationOS` folder into the existing repository, including `.github`, `.gitignore`, and `.vscode`.
8. Reopen the repository in VS Code.
9. Run the validation commands supplied with the release.

Never copy a `.git` folder from a release package. Release ZIPs do not contain one.
