# Atom Map Viewer

Small RDKit/Tkinter tool for visualizing SMILES, SMIRKS, or reaction-SMILES
strings with atom-map numbers shown as side annotations on each atom.

## Requirements

- Python 3.10+
- [RDKit](https://www.rdkit.org/)
- Pillow

```
pip install rdkit pillow
```

## Usage

### Single structure (edit the SMILES in the file)

```
python show_atom_map.py
```

Edit the `SMILES` constant near the top of [show_atom_map.py](show_atom_map.py) to change what's displayed.

### Applet (paste in a list of structures)

```
python atom_map_viewer_app.py
```

Paste SMILES/SMIRKS/reaction-SMILES strings into the text box (one per line,
or a row copied horizontally from a spreadsheet) and click **Render**. The
structures are drawn below and stack into a scrollable page. Click any
structure to open it full-size, with zoom and scroll controls.

## Building a standalone .exe

To share the applet with someone who doesn't have Python installed, bundle it
into a single Windows executable with [PyInstaller](https://pyinstaller.org/):

```
pip install pyinstaller
pyinstaller --onefile --windowed --name AtomMapViewer atom_map_viewer_app.py
```

The result is `dist/AtomMapViewer.exe` — a self-contained file (~40 MB,
since it bundles RDKit) that runs standalone. Share that one file; the
`build/` and `dist/` folders and the generated `.spec` file are safe to
delete/regenerate and aren't tracked in this repo.
