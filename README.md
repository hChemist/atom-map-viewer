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

Paste one SMILES/SMIRKS/reaction-SMILES string per line into the text box,
click **Render**, then use **Previous**/**Next** (or the Left/Right arrow
keys) to step through the rendered structures.
