<p align="center">
  <img src="assets/filesorter_ui.png" width="700">
</p>

# FileSorterApp

FileSorterApp is a desktop application that organizes files into user-defined folders
based on allowed file extensions. Built with **Python** and **PySide6**, the app
provides a clean UI and drag-and-drop support for easy file sorting.

---

## Features
- Custom folder rules by file extension  
- Drag-and-drop sorting box  
- Clean, modern UI built with Qt Designer  
- Rule management (add / edit / remove folders)  

---

## Setup (Virtual Environment)

### 1. Navigate to the project directory
Make sure your terminal is in the root folder:

    cd FileSorterApp

### 2. Select the virtual environment interpreter
In PyCharm:
- Go to **File / Settings / Python / Interpreter**
- Select the existing interpreter from the `.venv` folder

### 3. Restart the terminal
Close and reopen the terminal.  
You should now see something like:

    (.venv) PS C:\Users\...

This means you are in the virtual environment and are ready to run the program.
---

## Running the App

    python src/core/app_init.py
