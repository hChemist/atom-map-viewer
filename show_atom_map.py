"""
Display a SMILES (or reaction SMILES) string with atom-map numbers rendered on each atom.

Edit SMILES below, then run: python show_atom_map.py
Reaction SMILES (containing ">>") are detected automatically and rendered
as reactants -> products.
"""

import io

from PIL import Image
from rdkit import Chem
from rdkit.Chem import rdChemReactions
from rdkit.Chem.Draw import rdMolDraw2D

# Edit this to whatever SMILES (or reaction SMILES) you want to visualize.
SMILES = "CC(=O)[CH:2110]=[CH2:20].C1[CH:10]=[CH:11][CH:12]=[CH:13]O1>>CC(=O)[CH:21]1[CH2:20][CH:10]2CO[CH:22]1[CH:23]=[CH:24]2"

SIZE = 500


def _move_map_numbers_to_notes(mol) -> None:
    """Show atom-map numbers as small side annotations instead of inline in the atom label.

    Atoms with no explicit atom-map number are left unlabeled.
    """
    for atom in mol.GetAtoms():
        map_num = atom.GetAtomMapNum()
        if map_num != 0:
            atom.SetProp("atomNote", str(map_num))
            atom.SetAtomMapNum(0)


def _configure_draw_options(drawer) -> None:
    options = drawer.drawOptions()
    options.annotationFontScale = 0.85
    options.bondLineWidth = 2
    options.minFontSize = 14
    options.maxFontSize = 24


def render_mapped_smiles(smiles: str, size: int = 500) -> bytes:
    is_reaction = ">>" in smiles or (">" in smiles and smiles.count(">") >= 2)

    if is_reaction:
        rxn = rdChemReactions.ReactionFromSmarts(smiles, useSmiles=True)
        if rxn is None:
            raise ValueError(f"Could not parse reaction SMILES: {smiles!r}")

        mols = list(rxn.GetReactants()) + list(rxn.GetAgents()) + list(rxn.GetProducts())
        num_atoms = 0
        for mol in mols:
            mol.UpdatePropertyCache(strict=False)
            Chem.rdDepictor.Compute2DCoords(mol)
            _move_map_numbers_to_notes(mol)
            num_atoms += mol.GetNumAtoms()

        # Scale resolution up for bigger reactions so detail (and atom-map
        # notes) stay sharp instead of getting crammed into a fixed canvas.
        scale = max(1.0, num_atoms / 25)
        width, height = int(size * 3 * scale), int(size * scale)

        drawer = rdMolDraw2D.MolDraw2DCairo(width, height)
        _configure_draw_options(drawer)
        drawer.DrawReaction(rxn)
        drawer.FinishDrawing()
    else:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError(f"Could not parse SMILES: {smiles!r}")

        _move_map_numbers_to_notes(mol)

        scale = max(1.0, mol.GetNumAtoms() / 25)
        dimension = int(size * scale)

        drawer = rdMolDraw2D.MolDraw2DCairo(dimension, dimension)
        _configure_draw_options(drawer)
        rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
        drawer.FinishDrawing()

    return drawer.GetDrawingText()


def main() -> None:
    png_bytes = render_mapped_smiles(SMILES, SIZE)
    image = Image.open(io.BytesIO(png_bytes))
    image.show()


if __name__ == "__main__":
    main()
